import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        // 检查是否是因为会话失效（被踢下线）
        const detail = data?.detail || ''
        if (detail.includes('会话已失效') || detail.includes('其他地方登录')) {
          // 清除本地存储
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('token_expiry')
          sessionStorage.removeItem('user')
          
          // 显示提示消息
          ElMessage.error('您的账号已在其他地方登录，当前会话已失效')
          
          // 跳转到登录页
          window.location.href = '/login'
        } else {
          // 普通的 401 错误（token 过期或无效）
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('token_expiry')
          sessionStorage.removeItem('user')
          window.location.href = '/login'
        }
      } else if (status === 403) {
        ElMessage.error(data.detail || '权限不足')
      } else if (status === 429) {
        ElMessage.warning(data.detail || '请求过于频繁')
      } else {
        ElMessage.error(data.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default api
