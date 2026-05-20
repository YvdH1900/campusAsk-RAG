<template>
  <div class="profile-container">
    <div class="profile-wrapper">
      <div class="page-header">
        <div class="header-content">
          <div class="header-badge">
            <div class="badge-dot"></div>
            <span>USER PROFILE</span>
          </div>
          <h2 class="page-title">个人资料</h2>
          <p class="page-desc">管理你的个人信息和账户设置</p>
          <div class="header-line"></div>
        </div>
      </div>

      <div class="profile-card">
        <div class="card-glow"></div>
        <div class="profile-header">
          <div class="avatar-section">
            <div class="avatar-icon">
              <div class="avatar-glow"></div>
              <el-icon :size="40"><UserFilled /></el-icon>
            </div>
            <div class="user-info">
              <h2 class="username">{{ userStore.user?.username || '加载中...' }}</h2>
              <span class="role-badge" :class="userStore.user?.role">
                {{ getRoleLabel(userStore.user?.role) }}
              </span>
            </div>
          </div>
        </div>

        <div class="divider"></div>

        <form class="profile-form" @submit.prevent="handleSubmit">
          <div class="form-group">
            <label class="form-label">用户名</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><User /></el-icon>
              <input
                v-model="form.username"
                type="text"
                class="custom-input"
                placeholder="请输入用户名"
              />
            </div>
            <p v-if="errors.username" class="error-text">{{ errors.username }}</p>
          </div>

          <div class="form-group">
            <label class="form-label">邮箱</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Message /></el-icon>
              <input
                v-model="form.email"
                type="email"
                class="custom-input"
                placeholder="请输入邮箱"
              />
            </div>
            <p v-if="errors.email" class="error-text">{{ errors.email }}</p>
          </div>

          <div class="section-header">
            <div class="section-line"></div>
            <span class="section-title">修改密码</span>
            <div class="section-line"></div>
          </div>

          <div class="form-group">
            <label class="form-label">新密码</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <input
                v-model="form.password"
                type="password"
                class="custom-input"
                placeholder="留空则不修改密码"
              />
            </div>
            <p v-if="errors.password" class="error-text">{{ errors.password }}</p>
          </div>

          <div class="form-group">
            <label class="form-label">确认新密码</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <input
                v-model="form.confirmPassword"
                type="password"
                class="custom-input"
                placeholder="请再次输入新密码"
              />
            </div>
            <p v-if="errors.confirmPassword" class="error-text">{{ errors.confirmPassword }}</p>
          </div>

          <div class="form-actions">
            <button type="submit" class="submit-btn" :disabled="loading">
              <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
              <el-icon v-else><Check /></el-icon>
              <span>{{ loading ? '保存中...' : '保存修改' }}</span>
            </button>
            <button type="button" class="reset-btn" @click="handleReset">
              <el-icon><RefreshLeft /></el-icon>
              <span>重置</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UserFilled, User, Message, Lock, Check, RefreshLeft, Loading } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import axios from 'axios'

const userStore = useUserStore()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const errors = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const validateForm = () => {
  let isValid = true
  errors.username = ''
  errors.email = ''
  errors.password = ''
  errors.confirmPassword = ''

  if (!form.username || form.username.length < 2 || form.username.length > 20) {
    errors.username = '用户名长度在2-20个字符'
    isValid = false
  }

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = '请输入有效的邮箱地址'
    isValid = false
  }

  if (form.password && form.password.length < 6) {
    errors.password = '密码长度不能少于6位'
    isValid = false
  }

  if (form.password && form.password !== form.confirmPassword) {
    errors.confirmPassword = '两次输入的密码不一致'
    isValid = false
  }

  return isValid
}

const getRoleLabel = (role: any) => {
  const roleValue = typeof role === 'object' ? role?.value : role
  const roleMap: Record<string, string> = {
    student: '学生',
    teacher: '教师',
    admin: '管理员'
  }
  return roleMap[roleValue] || '未知'
}

const loadUserInfo = () => {
  if (userStore.user) {
    form.username = userStore.user.username
    form.email = userStore.user.email || ''
    form.password = ''
    form.confirmPassword = ''
  }
}

const handleSubmit = async () => {
  if (!validateForm()) return

  loading.value = true
  try {
    const updateData: any = {}
    
    if (form.username !== userStore.user?.username) {
      updateData.username = form.username
    }
    
    if (form.email !== userStore.user?.email) {
      updateData.email = form.email
    }
    
    if (form.password) {
      updateData.password = form.password
    }

    const response = await axios.put('/api/v1/auth/me', updateData, {
      headers: {
        Authorization: `Bearer ${userStore.token}`
      }
    })

    userStore.setUserInfo(response.data)
    ElMessage.success('个人信息更新成功')
    form.password = ''
    form.confirmPassword = ''
  } catch (error: any) {
    const message = error.response?.data?.detail || '更新失败，请重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  loadUserInfo()
  ElMessage.info('已重置表单')
}

onMounted(async () => {
  if (!userStore.user) {
    await userStore.fetchUser()
  }
  loadUserInfo()
})
</script>

<style scoped>
.profile-container {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: var(--space-6) var(--space-4);
  position: relative;
  overflow: hidden;
  min-height: calc(100vh - 64px);
  width: 100%;
}

.profile-wrapper {
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.page-header {
  width: 100%;
  margin-bottom: var(--space-8);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--primary-subtle);
  border: 1px solid rgba(0, 229, 160, 0.2);
  border-radius: var(--radius-xs);
  width: fit-content;
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--primary);
  letter-spacing: 0.05em;
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.page-title {
  font-size: var(--text-3xl);
  color: var(--text-primary);
  margin: 0;
  font-weight: var(--font-bold);
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.page-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

.header-line {
  height: 2px;
  background: linear-gradient(90deg, var(--primary) 0%, var(--accent) 100%);
  margin-top: var(--space-4);
  border-radius: 1px;
  opacity: 0.3;
}

.profile-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-2xl);
  padding: var(--space-8) var(--space-10);
  width: 100%;
  box-shadow: var(--shadow-xl);
  position: relative;
}

.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--primary) 50%, transparent 100%);
  opacity: 0.3;
}

.profile-header {
  margin-bottom: var(--space-6);
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.avatar-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  position: relative;
  transition: all var(--duration-normal) var(--ease-out);
}

.avatar-glow {
  position: absolute;
  inset: -4px;
  background: var(--primary);
  border-radius: inherit;
  opacity: 0;
  filter: blur(8px);
  transition: opacity var(--duration-normal) var(--ease-out);
}

.avatar-icon:hover {
  transform: scale(1.05);
}

.avatar-icon:hover .avatar-glow {
  opacity: 0.4;
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.username {
  color: var(--text-primary);
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  margin: 0;
  letter-spacing: -0.02em;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  width: fit-content;
}

.role-badge.student {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.role-badge.teacher {
  background: rgba(245, 158, 11, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.role-badge.admin {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.divider {
  height: 1px;
  background: var(--border-base);
  margin-bottom: var(--space-6);
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: var(--space-3);
  color: var(--text-tertiary);
  font-size: var(--text-base);
  pointer-events: none;
  transition: color var(--duration-fast) var(--ease-out);
}

.custom-input {
  width: 100%;
  height: 44px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4) var(--space-3) var(--space-10);
  color: var(--text-primary);
  font-size: var(--text-base);
  font-family: inherit;
  outline: none;
  transition: all var(--duration-normal) var(--ease-out);
  background-color: var(--bg-elevated) !important;
  -webkit-text-fill-color: var(--text-primary) !important;
}

.custom-input:hover {
  border-color: var(--border-hover);
}

.custom-input:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.custom-input:focus + .input-icon,
.input-wrapper:focus-within .input-icon {
  color: var(--primary);
}

.custom-input::placeholder {
  color: var(--text-muted);
}

.error-text {
  font-size: var(--text-xs);
  color: var(--accent);
  margin: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-2) 0;
}

.section-line {
  flex: 1;
  height: 1px;
  background: var(--border-base);
}

.section-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--font-medium);
}

.form-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-6);
  background: var(--primary);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.submit-btn:hover:not(:disabled) {
  background: var(--primary-light);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--primary-glow);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.reset-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-6);
  background: transparent;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--text-base);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.reset-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  color: var(--text-primary);
}
</style>
