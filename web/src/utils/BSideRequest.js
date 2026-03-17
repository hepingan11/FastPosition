import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

export let cancelArr = [];

const apiBaseUrl = process.env.VUE_APP_API_BASE_URL || 'http://localhost:8000'

const service = axios.create({
    baseURL: apiBaseUrl,
    timeout: 6 * 60 * 1000
});

service.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`
    }

    const isFormData = typeof FormData !== 'undefined' && config.data instanceof FormData
    if (!isFormData) {
        config.headers['Content-Type'] = 'application/json'
    } else if (config.headers['Content-Type']) {
        delete config.headers['Content-Type']
    }

    config.cancelToken = new axios.CancelToken(cancel => {
        cancelArr.push(cancel)
    })
    return config
}, error => {
    return Promise.reject(error)
});

service.interceptors.response.use(response => {
    return response.data
}, error => {
    if (error.response?.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
    } else {
        ElMessage.error(error.response?.data?.detail || error.message || '服务调用失败，请稍后使用。')
    }
    return Promise.reject(error)
})

export default service
