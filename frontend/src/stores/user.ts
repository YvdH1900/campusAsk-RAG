/**
 * 用户状态管理 Store
 * ==================
 * 使用 Pinia 管理用户登录状态、角色信息
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export type UserRole = 'student' | 'teacher' | 'admin'

export interface UserInfo {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export const useUserStore = defineStore('user', () => {
  // 使用 sessionStorage 替代 localStorage，关闭浏览器后自动清除
  const token = ref<string | null>(sessionStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role?.toLowerCase() === 'admin')
    const isTeacher = computed(() => user.value?.role?.toLowerCase() === 'teacher')

  async function login(username: string, password: string) {
    const response = await axios.post('/api/v1/auth/login', { username, password })
    token.value = response.data.access_token
    user.value = response.data.user
    
    // 使用 sessionStorage 存储 token，关闭浏览器后自动清除
    sessionStorage.setItem('token', response.data.access_token)
    
    // 设置 token 过期时间（1小时）
    const tokenExpiry = Date.now() + 60 * 60 * 1000 // 1小时
    sessionStorage.setItem('token_expiry', tokenExpiry.toString())
    
    // 启动定时器检查 token 过期
    startTokenExpiryCheck()
    
    return response.data
  }

  async function register(username: string, email: string, password: string, role: string = 'student') {
    await axios.post('/api/v1/auth/register', { username, email, password, role })
  }

  async function fetchUser() {
    if (!token.value) return
    // 跳过 token_expiry 检查，让服务端验证 token 是否有效
    try {
      const response = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      user.value = response.data
    } catch {
      logout()
    }
  }

  // 检查 token 是否过期
  function checkTokenExpiry() {
    const expiry = sessionStorage.getItem('token_expiry')
    if (expiry && Date.now() > parseInt(expiry)) {
      logout()
      return false
    }
    return true
  }

  // 启动 token 过期检查定时器
  function startTokenExpiryCheck() {
    // 每5分钟检查一次 token 是否过期
    setInterval(() => {
      checkTokenExpiry()
    }, 5 * 60 * 1000)
  }

  async function logout() {
    if (token.value) {
      try {
        await axios.post(
          '/api/v1/auth/logout',
          {},
          { headers: { Authorization: `Bearer ${token.value}` } },
        )
      } catch {
        // 忽略服务端错误，仍然清除本地状态
      }
    }
    token.value = null
    user.value = null
    
    // 清除 sessionStorage 中的 token 和过期时间
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('token_expiry')
    sessionStorage.removeItem('user')
  }

  function setUserInfo(info: UserInfo) {
    user.value = info
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    isTeacher,
    login,
    register,
    fetchUser,
    logout,
    setUserInfo,
  }
})
