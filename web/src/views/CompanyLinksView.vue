<template>
  <div class="company-links-container">
    <el-card class="company-links-card">
      <template #header>
        <div class="card-header">
          <el-icon><Link /></el-icon>
          <span class="title">公司链接管理</span>
        </div>
      </template>

      <div class="card-content">
        <div class="toolbar">
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加公司链接
          </el-button>
          <el-button
            type="success"
            :disabled="selectedRows.length === 0"
            :loading="crawlLoading"
            @click="handleBatchCrawl"
          >
            一键爬取选中公司
          </el-button>
        </div>

        <el-table
          :data="companyLinks"
          border
          stripe
          style="width: 100%"
          @selection-change="handleSelectionChange"
          @row-dblclick="handleEdit"
        >
          <el-table-column type="selection" width="55" align="center" />
          <el-table-column prop="id" label="ID" width="80" align="center" />
          <el-table-column prop="company_name" label="公司名称" min-width="200" />
          <el-table-column prop="link" label="公司链接" min-width="320" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="120" align="center">
            <template #default="scope">
              <el-tag :type="tagType(scope.row.type)">{{ scope.row.type || '其他' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="create_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="180" align="center">
            <template #default="scope">
              <el-button size="small" type="primary" @click="handleEdit(scope.row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
          class="pagination"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="公司名称" prop="company_name">
          <el-input v-model="form.company_name" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="公司链接" prop="link">
          <el-input v-model="form.link" placeholder="请输入公司链接" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择类型">
            <el-option label="校招" value="校招" />
            <el-option label="实习" value="实习" />
            <el-option label="应届" value="应届" />
            <el-option label="社招" value="社招" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="crawlProgressVisible" title="实时爬取进度" width="1100px">
      <div class="progress-header">
        <div class="progress-line">
          <span>状态：{{ taskStatusLabel }}</span>
          <span v-if="crawlTask.current_company_name">当前公司：{{ crawlTask.current_company_name }}</span>
        </div>
        <el-progress
          :percentage="progressPercentage"
          :status="crawlTask.status === 'failed' ? 'exception' : undefined"
        />
      </div>

      <el-table :data="crawlTask.results || []" border stripe max-height="360">
        <el-table-column prop="company_name" label="公司名称" min-width="180" />
        <el-table-column label="进度状态" width="120" align="center">
          <template #default="scope">
            <el-tag :type="resultTagType(scope.row)">
              {{ resultStatusLabel(scope.row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inserted" label="新增" width="90" align="center" />
        <el-table-column prop="updated" label="更新" width="90" align="center" />
        <el-table-column prop="message" label="说明" min-width="240" show-overflow-tooltip />
        <el-table-column label="详情" width="100" align="center">
          <template #default="scope">
            <el-button type="primary" link @click="showCrawlDetail(scope.row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="live-steps" v-if="liveCurrentResult">
        <div class="detail-title">当前公司实时步骤</div>
        <el-timeline>
          <el-timeline-item
            v-for="(step, index) in liveCurrentResult.debug_steps || []"
            :key="`${index}-${step}`"
          >
            {{ step }}
          </el-timeline-item>
        </el-timeline>
      </div>

      <template #footer>
        <el-button @click="crawlProgressVisible = false">关闭</el-button>
        <el-button
          v-if="crawlTask.status === 'completed'"
          type="primary"
          @click="openFinalResults"
        >
          查看最终结果
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="crawlResultVisible" title="批量爬取结果" width="1100px">
      <el-table :data="crawlResults" border stripe style="width: 100%">
        <el-table-column prop="company_name" label="公司名称" min-width="160" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.success ? 'success' : 'danger'">
              {{ scope.row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inserted" label="新增职位" width="100" align="center" />
        <el-table-column prop="updated" label="更新职位" width="100" align="center" />
        <el-table-column prop="message" label="结果说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="过程" width="120" align="center">
          <template #default="scope">
            <el-button type="primary" link @click="showCrawlDetail(scope.row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="crawlResultVisible = false">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="crawlDetailVisible" title="爬取过程详情" width="1100px">
      <template v-if="currentCrawlDetail">
        <el-descriptions :column="2" border class="detail-summary">
          <el-descriptions-item label="公司名称">{{ currentCrawlDetail.company_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentCrawlDetail.success ? 'success' : 'danger'">
              {{ currentCrawlDetail.success ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="新增职位">{{ currentCrawlDetail.inserted }}</el-descriptions-item>
          <el-descriptions-item label="更新职位">{{ currentCrawlDetail.updated }}</el-descriptions-item>
          <el-descriptions-item label="结果说明" :span="2">{{ currentCrawlDetail.message }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-block">
          <div class="detail-title">执行步骤</div>
          <el-timeline>
            <el-timeline-item
              v-for="(step, index) in currentCrawlDetail.debug_steps || []"
              :key="`${index}-${step}`"
            >
              {{ step }}
            </el-timeline-item>
          </el-timeline>
        </div>

        <div class="detail-block">
          <div class="detail-title">解析出的职位</div>
          <el-table :data="currentCrawlDetail.extracted_positions || []" border stripe max-height="260">
            <el-table-column prop="name" label="职位名称" min-width="180" />
            <el-table-column prop="location" label="地点" width="140" />
            <el-table-column prop="salary" label="薪资" width="140" />
            <el-table-column prop="link" label="链接" min-width="260" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="detail-block">
          <div class="detail-title">页面文本预览</div>
          <pre class="detail-pre">{{ currentCrawlDetail.page_text_preview || '无' }}</pre>
        </div>

        <div class="detail-block">
          <div class="detail-title">LLM 或接口原始返回</div>
          <pre class="detail-pre">{{ currentCrawlDetail.llm_raw_response || '无' }}</pre>
        </div>
      </template>
      <template #footer>
        <el-button type="primary" @click="crawlDetailVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCompanyLink,
  deleteCompanyLink,
  getBatchCrawlTaskStatus,
  getCompanyLinks,
  startBatchCrawlCompanyLinks,
  updateCompanyLink
} from '@/api/companyLinks'

export default {
  name: 'CompanyLinksView',
  setup() {
    const companyLinks = ref([])
    const total = ref(0)
    const currentPage = ref(1)
    const pageSize = ref(10)
    const dialogVisible = ref(false)
    const dialogTitle = ref('添加公司链接')
    const formRef = ref(null)
    const selectedRows = ref([])
    const crawlLoading = ref(false)
    const crawlResultVisible = ref(false)
    const crawlResults = ref([])
    const crawlDetailVisible = ref(false)
    const currentCrawlDetail = ref(null)
    const crawlProgressVisible = ref(false)
    const crawlTask = ref({
      task_id: '',
      status: 'idle',
      total: 0,
      completed: 0,
      success_count: 0,
      failure_count: 0,
      current_company_name: '',
      results: []
    })
    let pollTimer = null

    const form = reactive({
      id: null,
      company_name: '',
      link: '',
      type: null
    })

    const rules = {
      company_name: [
        { required: true, message: '请输入公司名称', trigger: 'blur' },
        { min: 2, max: 150, message: '公司名称长度在 2 到 150 个字符', trigger: 'blur' }
      ],
      link: [
        { required: true, message: '请输入公司链接', trigger: 'blur' },
        { min: 5, message: '公司链接长度至少 5 个字符', trigger: 'blur' }
      ]
    }

    const tagType = (type) => {
      if (type === '校招') return 'success'
      if (type === '实习') return 'primary'
      if (type === '应届') return 'warning'
      if (type === '社招') return 'info'
      return 'default'
    }

    const progressPercentage = computed(() => {
      if (!crawlTask.value.total) return 0
      return Math.min(100, Math.round((crawlTask.value.completed / crawlTask.value.total) * 100))
    })

    const taskStatusLabel = computed(() => {
      if (crawlTask.value.status === 'pending') return '等待中'
      if (crawlTask.value.status === 'running') return '执行中'
      if (crawlTask.value.status === 'completed') return '已完成'
      if (crawlTask.value.status === 'failed') return '失败'
      return '未开始'
    })

    const liveCurrentResult = computed(() => {
      const currentCompanyName = crawlTask.value.current_company_name
      if (!currentCompanyName) return null
      return (crawlTask.value.results || []).find((item) => item.company_name === currentCompanyName) || null
    })

    const fetchData = async () => {
      try {
        const res = await getCompanyLinks({
          skip: (currentPage.value - 1) * pageSize.value,
          limit: pageSize.value
        })
        companyLinks.value = res
        total.value = res.length
      } catch (error) {
        ElMessage.error('获取公司链接失败')
      }
    }

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const refreshTaskStatus = async (taskId) => {
      const task = await getBatchCrawlTaskStatus(taskId)
      crawlTask.value = task
      if (task.status === 'completed' || task.status === 'failed') {
        stopPolling()
        crawlLoading.value = false
        crawlResults.value = task.results || []
        if (task.status === 'completed') {
          ElMessage.success(`批量爬取完成，成功 ${task.success_count} 家，失败 ${task.failure_count} 家`)
        } else {
          ElMessage.error(task.error_message || '批量爬取失败')
        }
      }
    }

    const startPolling = (taskId) => {
      stopPolling()
      pollTimer = setInterval(() => {
        refreshTaskStatus(taskId).catch(() => {})
      }, 1500)
    }

    const handleAdd = () => {
      dialogVisible.value = true
      dialogTitle.value = '添加公司链接'
      form.id = null
      form.company_name = ''
      form.link = ''
      form.type = null
    }

    const handleEdit = (row) => {
      dialogVisible.value = true
      dialogTitle.value = '编辑公司链接'
      form.id = row.id
      form.company_name = row.company_name
      form.link = row.link
      form.type = row.type
    }

    const handleDelete = async (row) => {
      try {
        await ElMessageBox.confirm('确定要删除该公司链接吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteCompanyLink(row.id)
        ElMessage.success('删除成功')
        await fetchData()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }

    const handleSelectionChange = (rows) => {
      selectedRows.value = rows
    }

    const resultTagType = (row) => {
      if (row.status === 'running') return 'warning'
      return row.success ? 'success' : 'danger'
    }

    const resultStatusLabel = (row) => {
      if (row.status === 'running') return '进行中'
      return row.success ? '成功' : '失败'
    }

    const showCrawlDetail = (row) => {
      currentCrawlDetail.value = row
      crawlDetailVisible.value = true
    }

    const openFinalResults = () => {
      crawlResultVisible.value = true
    }

    const handleBatchCrawl = async () => {
      if (selectedRows.value.length === 0) {
        ElMessage.warning('请先选择公司')
        return
      }

      try {
        await ElMessageBox.confirm(
          `确定要爬取已选中的 ${selectedRows.value.length} 家公司吗？`,
          '提示',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        crawlLoading.value = true
        const res = await startBatchCrawlCompanyLinks(selectedRows.value.map((item) => item.id))
        crawlTask.value = {
          task_id: res.task_id,
          status: res.status,
          total: selectedRows.value.length,
          completed: 0,
          success_count: 0,
          failure_count: 0,
          current_company_name: '',
          results: []
        }
        crawlProgressVisible.value = true
        await refreshTaskStatus(res.task_id)
        if (crawlTask.value.status !== 'completed' && crawlTask.value.status !== 'failed') {
          startPolling(res.task_id)
        }
      } catch (error) {
        if (error !== 'cancel') {
          crawlLoading.value = false
          ElMessage.error(error.response?.data?.detail || '批量爬取失败')
        }
      }
    }

    const handleSubmit = async () => {
      if (!formRef.value) return
      await formRef.value.validate(async (valid) => {
        if (!valid) return
        try {
          if (form.id) {
            await updateCompanyLink(form.id, form)
            ElMessage.success('编辑成功')
          } else {
            await createCompanyLink(form)
            ElMessage.success('添加成功')
          }
          dialogVisible.value = false
          await fetchData()
        } catch (error) {
          ElMessage.error(error.response?.data?.detail || '操作失败')
        }
      })
    }

    const handleSizeChange = (val) => {
      pageSize.value = val
      currentPage.value = 1
      fetchData()
    }

    const handleCurrentChange = (val) => {
      currentPage.value = val
      fetchData()
    }

    onMounted(() => {
      fetchData()
    })

    onBeforeUnmount(() => {
      stopPolling()
    })

    return {
      companyLinks,
      total,
      currentPage,
      pageSize,
      dialogVisible,
      dialogTitle,
      formRef,
      selectedRows,
      crawlLoading,
      crawlResultVisible,
      crawlResults,
      crawlDetailVisible,
      currentCrawlDetail,
      crawlProgressVisible,
      crawlTask,
      progressPercentage,
      taskStatusLabel,
      liveCurrentResult,
      form,
      rules,
      tagType,
      resultTagType,
      resultStatusLabel,
      handleAdd,
      handleEdit,
      handleDelete,
      handleSelectionChange,
      handleBatchCrawl,
      handleSubmit,
      handleSizeChange,
      handleCurrentChange,
      showCrawlDetail,
      openFinalResults
    }
  }
}
</script>

<style scoped>
.company-links-container {
  padding: 20px;
}

.company-links-card {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.progress-header {
  margin-bottom: 16px;
}

.progress-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #606266;
}

.live-steps,
.detail-summary,
.detail-block {
  margin-top: 16px;
}

.detail-title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.detail-pre {
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 8px;
  background: #f6f8fa;
  color: #1f2328;
  line-height: 1.6;
}
</style>
