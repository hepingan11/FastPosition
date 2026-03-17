<template>
  <div class="positions-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isRecommendationMode ? '智能推荐结果' : '职位推荐' }}</span>
        </div>
      </template>
      
      <el-alert
        v-if="isRecommendationMode"
        title="当前展示基于已上传简历的推荐结果"
        type="success"
        :closable="false"
        style="margin-bottom: 16px;"
      />

      <el-form v-if="!isRecommendationMode" :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="公司">
          <el-input v-model="searchForm.company" placeholder="请输入公司名称" clearable />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="searchForm.location" placeholder="请输入工作地点" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card style="margin-top: 24px;">
      <el-table :data="positions" style="width: 100%" v-loading="loading">
        <el-table-column prop="name" label="职位名称" min-width="200" />
        <el-table-column v-if="isRecommendationMode" prop="match_score" label="匹配度" width="100">
          <template #default="{ row }">
            <el-tag :type="scoreTagType(row.match_score)">{{ row.match_score ?? 0 }}分</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="company" label="公司" width="150" />
        <el-table-column prop="job_type" label="招聘类型" width="110" />
        <el-table-column prop="location" label="地点" width="120" />
        <el-table-column prop="salary" label="薪资" width="120" />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column v-if="isRecommendationMode" prop="match_reason" label="推荐理由" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="row.link" type="success" size="small" @click="apply(row)">投递</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-if="!isRecommendationMode"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadPositions"
        style="margin-top: 24px; justify-content: center"
      />
    </el-card>
    
    <el-dialog v-model="detailVisible" title="职位详情" width="600px">
      <div v-if="currentPosition">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="职位名称">{{ currentPosition.name }}</el-descriptions-item>
          <el-descriptions-item label="公司">{{ currentPosition.company }}</el-descriptions-item>
          <el-descriptions-item label="招聘类型">{{ currentPosition.job_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地点">{{ currentPosition.location }}</el-descriptions-item>
          <el-descriptions-item label="薪资">{{ currentPosition.salary }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ currentPosition.source }}</el-descriptions-item>
          <el-descriptions-item v-if="isRecommendationMode && currentPosition.match_score !== undefined" label="匹配度">
            {{ currentPosition.match_score }}分
          </el-descriptions-item>
          <el-descriptions-item v-if="isRecommendationMode && currentPosition.match_reason" label="推荐理由">
            {{ currentPosition.match_reason }}
          </el-descriptions-item>
          <el-descriptions-item label="职位描述">
            <div style="white-space: pre-wrap;">{{ currentPosition.jd }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="currentPosition?.link" type="primary" @click="apply(currentPosition)">立即投递</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPositions, recommendPositions } from '@/api/position'

const route = useRoute()
const positions = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchForm = ref({
  company: '',
  location: ''
})
const detailVisible = ref(false)
const currentPosition = ref(null)
const isRecommendationMode = computed(() => Boolean(route.query.resumeId))
const resumeId = computed(() => route.query.resumeId)

const loadPositions = async () => {
  loading.value = true
  try {
    const res = isRecommendationMode.value
      ? await recommendPositions(resumeId.value)
      : await getPositions({
          skip: (currentPage.value - 1) * pageSize.value,
          limit: pageSize.value,
          company: searchForm.value.company,
          location: searchForm.value.location
        })
    positions.value = res.positions
    total.value = res.total
  } catch (error) {
    ElMessage.error(isRecommendationMode.value ? '加载推荐结果失败' : '加载职位列表失败')
  } finally {
    loading.value = false
  }
}

const search = () => {
  currentPage.value = 1
  loadPositions()
}

const reset = () => {
  searchForm.value = {
    company: '',
    location: ''
  }
  currentPage.value = 1
  loadPositions()
}

const scoreTagType = (score = 0) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'info'
}

const viewDetail = (row) => {
  currentPosition.value = row
  detailVisible.value = true
}

const apply = (row) => {
  if (row.link) {
    window.open(row.link, '_blank')
  }
}

onMounted(() => {
  loadPositions()
})

watch(
  () => route.query.resumeId,
  () => {
    currentPage.value = 1
    detailVisible.value = false
    currentPosition.value = null
    loadPositions()
  }
)
</script>

<style scoped>
.positions-page {
  max-width: 1000px;
  margin: 0 auto;
}

.card-header {
  font-size: 16px;
  font-weight: bold;
}

.search-form {
  margin-bottom: 0;
}
</style>
