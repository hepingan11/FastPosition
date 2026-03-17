<template>
  <div class="resume-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>简历上传</span>
        </div>
      </template>
      
      <el-upload
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        accept=".txt,.pdf"
        :limit="1"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            当前支持 txt, pdf 格式
          </div>
        </template>
      </el-upload>
      
      <div v-if="uploading" style="margin-top: 20px;">
        <el-progress :percentage="uploadProgress" />
        <p style="text-align: center; margin-top: 10px;">正在分析简历...</p>
      </div>
      
      <div v-if="parseResult" class="parse-result">
        <el-divider content-position="left">解析结果</el-divider>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-if="parseResult.name" label="姓名">{{ parseResult.name }}</el-descriptions-item>
          <el-descriptions-item v-if="parseResult.education" label="教育背景">{{ parseResult.education }}</el-descriptions-item>
          <el-descriptions-item v-if="parseResult.location" label="期望地点">{{ parseResult.location }}</el-descriptions-item>
          <el-descriptions-item v-if="parseResult.target_positions?.length" label="目标岗位">
            <el-tag v-for="position in parseResult.target_positions" :key="position" style="margin-right: 8px;">{{ position }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="parseResult.skills" label="技能">
            <el-tag v-for="skill in parseResult.skills" :key="skill" style="margin-right: 8px;">{{ skill }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="parseResult.experience" label="工作经历">{{ parseResult.experience }}</el-descriptions-item>
          <el-descriptions-item v-if="parseResult.summary" label="个人简介">{{ parseResult.summary }}</el-descriptions-item>
        </el-descriptions>
        <div class="actions">
          <el-button type="primary" @click="goToRecommendations(latestResumeId)">查看职位推荐</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card style="margin-top: 24px;">
      <template #header>
        <div class="card-header">
          <span>简历列表</span>
        </div>
      </template>
      
      <el-table :data="resumes" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewResume(row)">查看</el-button>
            <el-button v-if="row.file_url" size="small" @click="openOriginalFile(row.file_url)">原文件</el-button>
            <el-button type="success" size="small" @click="goToRecommendations(row.id)">推荐</el-button>
            <el-button type="danger" size="small" @click="deleteResume(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadResume, getResumes, deleteResume as deleteResumeApi } from '@/api/resume'

const router = useRouter()
const fileList = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const parseResult = ref(null)
const resumes = ref([])
const latestResumeId = ref(null)

const handleFileChange = async (file) => {
  if (file.status === 'ready') {
    await uploadFile(file.raw)
  }
}

const uploadFile = async (file) => {
  uploading.value = true
  uploadProgress.value = 0
  parseResult.value = null
  
  try {
    const res = await uploadResume(file, (progressEvent) => {
      uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
    })
    
    uploadProgress.value = 100
    ElMessage.success('简历上传成功！')
    latestResumeId.value = res.id
    
    if (res.parsed_info) {
      parseResult.value = res.parsed_info
    }
    
    await loadResumes()
  } catch (error) {
    ElMessage.error('上传失败: ' + error.message)
  } finally {
    uploading.value = false
  }
}

const loadResumes = async () => {
  try {
    const res = await getResumes()
    resumes.value = res.resumes
  } catch (error) {
    ElMessage.error('加载简历列表失败')
  }
}

const viewResume = (row) => {
  const preview = [row.content || '暂无内容']
  if (row.file_url) {
    preview.unshift(`原始简历文件：${row.file_url}`)
  }
  ElMessageBox.alert(preview.join('\n\n'), row.file_name, {
    confirmButtonText: '确定'
  })
}

const openOriginalFile = (fileUrl) => {
  if (!fileUrl) {
    ElMessage.warning('该简历暂无原文件链接')
    return
  }
  window.open(fileUrl, '_blank')
}

const goToRecommendations = (resumeId) => {
  if (!resumeId) {
    ElMessage.warning('未找到可推荐的简历')
    return
  }
  router.push({ path: '/positions', query: { resumeId } })
}

const deleteResume = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这个简历吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await deleteResumeApi(row.id)
    ElMessage.success('删除成功')
    await loadResumes()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadResumes()
})
</script>

<style scoped>
.resume-page {
  max-width: 900px;
  margin: 0 auto;
}

.card-header {
  font-size: 16px;
  font-weight: bold;
}

.parse-result {
  margin-top: 24px;
}

.actions {
  margin-top: 16px;
}
</style>
