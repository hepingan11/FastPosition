<template>
  <el-container class="layout-container">
    <el-header class="layout-header">
      <div class="header-content">
        <div class="logo">
          <el-icon><Promotion /></el-icon>
          <span>速速投</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          mode="horizontal"
          :ellipsis="false"
          @select="handleMenuSelect"
          class="nav-menu"
        >
          <el-menu-item index="/resume">
            <el-icon><Document /></el-icon>
            <span>简历管理</span>
          </el-menu-item>
          <el-menu-item index="/positions">
            <el-icon><Briefcase /></el-icon>
            <span>职位推荐</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能对话</span>
          </el-menu-item>
          <el-menu-item index="/company-links">
            <el-icon><Link /></el-icon>
            <span>公司链接管理</span>
          </el-menu-item>
        </el-menu>
        <div class="user-info">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              <el-icon><User /></el-icon>
              {{ user?.username }}
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>
    <el-main class="layout-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script>
import { computed, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'

export default {
  name: 'MainLayout',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const user = ref(null)

    const activeMenu = computed(() => route.path)

    const handleMenuSelect = (index) => {
      router.push(index)
    }

    const handleCommand = async (command) => {
      if (command === 'logout') {
        try {
          await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          })
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          user.value = null
          ElMessage.success('已退出登录')
          router.push('/login')
        } catch (error) {
          if (error !== 'cancel') {
            ElMessage.error('退出失败')
          }
        }
      }
    }

    onMounted(() => {
      const userStr = localStorage.getItem('user')
      if (userStr) {
        try {
          user.value = JSON.parse(userStr)
        } catch (e) {
          console.error('解析用户信息失败', e)
        }
      }
    })

    return {
      user,
      activeMenu,
      handleMenuSelect,
      handleCommand
    }
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-header {
  background-color: #409eff;
  color: #fff;
  padding: 0;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 20px;
}

.logo {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: bold;
  gap: 8px;
}

.nav-menu {
  flex: 1;
  justify-content: center;
  background-color: transparent;
}

.nav-menu .el-menu-item {
  color: #fff;
}

.nav-menu .el-menu-item.is-active {
  color: #fff;
  background-color: rgba(255, 255, 255, 0.2);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.el-dropdown-link {
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.layout-main {
  background-color: #f5f7fa;
  padding: 20px;
}
</style>