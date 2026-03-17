<template>
  <div class="chat-page">
    <el-card class="chat-card">
      <template #header>
        <div class="card-header">
          <span>智能对话</span>
          <el-button type="danger" size="small" @click="clearSession">清除会话</el-button>
        </div>
      </template>
      
      <div class="chat-container" ref="chatContainer">
        <div class="message-list">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-avatar">
              <el-icon v-if="message.role === 'user'"><User /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">{{ message.content }}</div>
            </div>
          </div>
          
          <div v-if="loading" class="message assistant">
            <div class="message-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="chat-input">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="请输入您的问题..."
          @keydown.enter.ctrl="sendMessage"
        />
        <div class="input-actions">
          <span class="hint">Ctrl + Enter 发送</span>
          <el-button type="primary" :loading="loading" @click="sendMessage">发送</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, ChatDotRound } from '@element-plus/icons-vue'
import { sendMessage as sendMessageApi, getChatHistory, clearChatSession } from '@/api/chat'

const chatContainer = ref(null)
const sessionId = ref('session_' + Date.now())
const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)

const loadHistory = async () => {
  try {
    const res = await getChatHistory(sessionId.value)
    messages.value = res.messages || []
    scrollToBottom()
  } catch (error) {
    console.error('加载历史记录失败', error)
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || loading.value) return
  
  const userContent = inputMessage.value
  inputMessage.value = ''
  
  messages.value.push({
    role: 'user',
    content: userContent
  })
  scrollToBottom()
  
  loading.value = true
  try {
    const res = await sendMessageApi({
      session_id: sessionId.value,
      message: userContent
    })
    
    messages.value.push({
      role: 'assistant',
      content: res.response
    })
    scrollToBottom()
  } catch (error) {
    ElMessage.error('发送失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const clearSession = async () => {
  try {
    await ElMessageBox.confirm('确定要清除当前会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await clearChatSession(sessionId.value)
    sessionId.value = 'session_' + Date.now()
    messages.value = []
    ElMessage.success('会话已清除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清除失败')
    }
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.chat-page {
  max-width: 900px;
  margin: 0 auto;
  height: calc(100vh - 120px);
}

.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: #f5f7fa;
}

.message-list {
  max-width: 800px;
  margin: 0 auto;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background-color: #409eff;
  color: white;
}

.message.assistant .message-avatar {
  background-color: #67c23a;
  color: white;
}

.message-content {
  max-width: 70%;
}

.message-text {
  padding: 12px 16px;
  border-radius: 8px;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  line-height: 1.6;
}

.message.user .message-text {
  background-color: #409eff;
  color: white;
}

.typing {
  display: flex;
  gap: 4px;
  padding: 16px;
}

.typing span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #909399;
  animation: typing 1.4s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
}

.chat-input {
  padding: 20px;
  border-top: 1px solid #ebeef5;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.hint {
  color: #909399;
  font-size: 12px;
}
</style>
