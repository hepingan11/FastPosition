import { createRouter, createWebHashHistory } from 'vue-router'
import { cancelArr } from "@/utils/BSideRequest"

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue'),
    meta: { title: '注册', requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/resume',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'resume',
        name: 'Resume',
        component: () => import('../views/ResumeView.vue'),
        meta: { title: '简历管理', requiresAuth: true }
      },
      {
        path: 'positions',
        name: 'Positions',
        component: () => import('../views/PositionsView.vue'),
        meta: { title: '职位推荐', requiresAuth: true }
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: '智能对话', requiresAuth: true }
      },
      {
        path: 'company-links',
        name: 'CompanyLinks',
        component: () => import('../views/CompanyLinksView.vue'),
        meta: { title: '公司链接管理', requiresAuth: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach(async (to) => {
  cancelArr.forEach((cancel, index) => {
    cancel()
    cancelArr.splice(index, 1)
  })

  document.title = (to.meta.title ? to.meta.title : '') + ' - FastPosition'

  const token = localStorage.getItem('token')
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !token) {
    return '/login'
  }

  if ((to.path === '/login' || to.path === '/register') && token) {
    return '/'
  }
})

export default router