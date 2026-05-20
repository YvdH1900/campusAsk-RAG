<template>
  <div class="login-container">
    <div class="bg-animation">
      <div class="aurora-orb orb-1"></div>
      <div class="aurora-orb orb-2"></div>
      <div class="aurora-orb orb-3"></div>
      <div class="perspective-grid"></div>
      <div class="line-decoration line-1"></div>
      <div class="line-decoration line-2"></div>
    </div>

    <div class="login-card">
      <!-- 公告弹窗 -->
      <el-dialog
        v-model="showAnnouncementDialog"
        :title="currentAnnouncement?.title || '公告'"
        width="500px"
        :close-on-click-modal="false"
        :show-close="false"
        class="announcement-dialog"
      >
        <div class="announcement-content">
          <p>{{ currentAnnouncement?.content }}</p>
        </div>
        <template #footer>
          <div class="dialog-footer">
            <el-button type="primary" @click="closeAnnouncement">
              我知道了
            </el-button>
          </div>
        </template>
      </el-dialog>
      <div class="login-left">
        <div class="aurora-line-top"></div>
        <div class="brand-section">
          <div class="brand-badge">
            <div class="badge-dot"></div>
            <span>CAMPUS SYSTEM</span>
          </div>
          
          <div class="brand-icon">
            <div class="icon-glow"></div>
            <el-icon :size="40"><ChatDotRound /></el-icon>
          </div>
          
          <h1 class="brand-title">
            <span class="title-part title-part-1">校园</span>
            <span class="title-part title-part-2 text-gradient">知识库</span>
          </h1>
          
          <div class="brand-divider"></div>
          
          <p class="brand-desc">智能问答助手</p>
          
          <div class="features">
            <div class="feature-header">
              <div class="feature-line"></div>
              <span class="feature-label">核心功能</span>
              <div class="feature-line"></div>
            </div>
            <div class="feature-item">
              <div class="feature-number">01</div>
              <div class="feature-content">
                <span>基于校园知识库精准回答</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-number">02</div>
              <div class="feature-content">
                <span>支持多种文档格式上传</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-number">03</div>
              <div class="feature-content">
                <span>智能语义检索匹配</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="login-right">
        <div class="aurora-line-right"></div>
        <div class="form-header">
          <h2 class="form-title">欢迎回来</h2>
          <div class="form-divider"></div>
          <p class="form-subtitle">登录以继续使用服务</p>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs">
          <el-tab-pane label="登录" name="login">
            <el-form
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              @submit.prevent="handleLogin"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="loginForm.username"
                  placeholder="请输入用户名"
                  :prefix-icon="User"
                  size="large"
                />
              </el-form-item>

              <el-form-item prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  placeholder="请输入密码"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  @keyup.enter="handleLogin"
                />
              </el-form-item>

              <el-form-item>
                <el-button
                  type="primary"
                  size="large"
                  class="submit-btn"
                  :loading="loading"
                  @click="handleLogin"
                >
                  <div class="btn-bg"></div>
                  <span class="btn-text">登 录</span>
                </el-button>
              </el-form-item>

              <div class="forgot-password-link">
                <router-link to="/forgot-password">忘记密码？</router-link>
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              @submit.prevent="handleRegister"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="registerForm.username"
                  placeholder="请输入用户名"
                  :prefix-icon="User"
                  size="large"
                />
              </el-form-item>

              <el-form-item prop="email">
                <el-input
                  v-model="registerForm.email"
                  placeholder="请输入邮箱"
                  :prefix-icon="Message"
                  size="large"
                />
              </el-form-item>

              <el-form-item prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  placeholder="请输入密码"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                />
              </el-form-item>

              <el-form-item prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  placeholder="请确认密码"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  @keyup.enter="handleRegister"
                />
              </el-form-item>

              <el-form-item prop="role">
                <el-select
                  v-model="registerForm.role"
                  placeholder="请选择注册身份"
                  size="large"
                  style="width: 100%"
                >
                  <el-option label="学生" value="student" />
                  <el-option label="教师（需管理员审核）" value="teacher" />
                </el-select>
              </el-form-item>

              <el-form-item>
                <el-button
                  type="primary"
                  size="large"
                  class="submit-btn"
                  :loading="loading"
                  @click="handleRegister"
                >
                  <div class="btn-bg"></div>
                  <span class="btn-text">注 册</span>
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Message, ChatDotRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 公告相关
const showAnnouncementDialog = ref(false)
const currentAnnouncement = ref<any>(null)
const announcementsQueue = ref<any[]>([])

onMounted(async () => {
  await loadAnnouncements()
})

const loadAnnouncements = async () => {
  try {
    const token = sessionStorage.getItem('token')
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch('/api/v1/admin/announcements/active', {
      headers
    })
    if (response.ok) {
      const data = await response.json()
      if (Array.isArray(data) && data.length > 0) {
        // 过滤出需要显示的公告
        const toShow = data.filter(item => {
          if (item.show_once) {
            const hasShown = sessionStorage.getItem(`announcement_shown_${item.id}`)
            return !hasShown
          }
          return true
        })
        
        if (toShow.length > 0) {
          announcementsQueue.value = toShow
          showNextAnnouncement()
        }
      }
    }
  } catch (error) {
    console.error('加载公告失败:', error)
  }
}

const showNextAnnouncement = () => {
  if (announcementsQueue.value.length > 0) {
    currentAnnouncement.value = announcementsQueue.value[0]
    showAnnouncementDialog.value = true
  }
}

const closeAnnouncement = () => {
  if (currentAnnouncement.value) {
    // 标记为已显示
    if (currentAnnouncement.value.show_once) {
      sessionStorage.setItem(`announcement_shown_${currentAnnouncement.value.id}`, 'true')
    }
    // 从队列中移除
    announcementsQueue.value.shift()
    showAnnouncementDialog.value = false
    currentAnnouncement.value = null
    
    // 显示下一个公告
    if (announcementsQueue.value.length > 0) {
      setTimeout(() => {
        showNextAnnouncement()
      }, 300)
    }
  }
}

const activeTab = ref('login')
const loading = ref(false)

const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  role: 'student',
})

const loginRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为 2-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为 2-20 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true

  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    // 根据用户角色进行分流
    if (userStore.isAdmin) {
      router.push('/admin')
    } else {
      router.push('/')
    }
  } catch (error: any) {
    const msg = error.response?.data?.detail || '登录失败，请检查用户名和密码'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true

  try {
    await userStore.register(registerForm.username, registerForm.email, registerForm.password, registerForm.role)
    
    if (registerForm.role === 'teacher') {
      ElMessage.success('注册成功，请等待管理员审核通过后再登录')
    } else {
      ElMessage.success('注册成功，请登录')
    }
    
    activeTab.value = 'login'
    loginForm.username = registerForm.username
  } catch (error: any) {
    const msg = error.response?.data?.detail || '注册失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-base);
  position: relative;
  overflow: hidden;
  padding: var(--space-5);
}

.bg-animation {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.aurora-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.3;
  animation: orbFloat 25s var(--ease-in-out) infinite;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(0, 229, 160, 0.4) 0%, transparent 70%);
  top: -200px;
  right: -100px;
  animation-delay: 0s;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(0, 180, 216, 0.35) 0%, transparent 70%);
  bottom: -150px;
  left: -100px;
  animation-delay: -8s;
}

.orb-3 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(123, 97, 255, 0.25) 0%, transparent 70%);
  top: 50%;
  left: 40%;
  animation-delay: -16s;
}

@keyframes orbFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -50px) scale(1.1); }
  66% { transform: translate(-30px, 30px) scale(0.9); }
}

.perspective-grid {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%) perspective(800px) rotateX(60deg);
  width: 200%;
  height: 50%;
  background-image: 
    linear-gradient(rgba(0, 229, 160, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 229, 160, 0.04) 1px, transparent 1px);
  background-size: 100px 100px;
  pointer-events: none;
  mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.2) 0%, transparent 100%);
}

.line-decoration {
  position: absolute;
  background: var(--gradient-aurora);
  opacity: 0.15;
}

.line-1 {
  width: 2px;
  height: 200px;
  top: 10%;
  left: 15%;
  transform: rotate(45deg);
}

.line-2 {
  width: 300px;
  height: 2px;
  bottom: 20%;
  right: 10%;
}

.login-card {
  width: 960px;
  max-width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-2xl);
  display: flex;
  overflow: hidden;
  box-shadow: var(--shadow-xl), var(--shadow-aurora);
  position: relative;
  z-index: 1;
}

.login-left {
  flex: 1;
  background: var(--bg-elevated);
  padding: var(--space-12) var(--space-10);
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid var(--border-base);
  position: relative;
  overflow: hidden;
}

.aurora-line-top {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--gradient-aurora);
  opacity: 0.6;
}

.brand-section {
  position: relative;
  z-index: 1;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  margin-bottom: var(--space-6);
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

.brand-badge span {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: var(--font-bold);
  letter-spacing: 0.15em;
}

.brand-icon {
  width: 56px;
  height: 56px;
  background: var(--primary-gradient);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0A0E17;
  margin-bottom: var(--space-6);
  position: relative;
  transition: all var(--duration-normal) var(--ease-spring);
}

.icon-glow {
  position: absolute;
  inset: -3px;
  background: var(--primary-gradient);
  border-radius: inherit;
  opacity: 0;
  filter: blur(10px);
  transition: opacity var(--duration-normal) var(--ease-out);
  z-index: -1;
}

.brand-icon:hover {
  transform: scale(1.08) rotate(-5deg);
}

.brand-icon:hover .icon-glow {
  opacity: 0.5;
}

.brand-title {
  font-size: var(--text-3xl);
  margin: 0 0 var(--space-3);
  font-weight: var(--font-ultra);
  letter-spacing: -0.03em;
  line-height: 1.1;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.title-part {
  display: block;
  line-height: 1;
}

.title-part-1 {
  color: var(--text-primary);
  transform: skewY(-2deg);
}

.title-part-2 {
  transform: skewY(2deg) translateX(10px);
}

.brand-divider {
  width: 80px;
  height: 3px;
  background: var(--gradient-aurora);
  margin-bottom: var(--space-3);
  border-radius: var(--radius-full);
}

.brand-desc {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0 0 var(--space-8);
  font-weight: var(--font-medium);
}

.features {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.feature-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.feature-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--border-base) 50%, transparent 100%);
}

.feature-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  white-space: nowrap;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.feature-item:hover {
  border-color: var(--border-hover);
  transform: translateX(var(--space-2));
}

.feature-number {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-bold);
  letter-spacing: 0.1em;
  opacity: 0.6;
  min-width: 24px;
}

.feature-content {
  flex: 1;
}

.feature-content span {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  transition: color var(--duration-fast) var(--ease-out);
}

.feature-item:hover .feature-content span {
  color: var(--text-primary);
}

.login-right {
  flex: 1;
  padding: var(--space-10);
  position: relative;
}

.aurora-line-right {
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  background: var(--gradient-aurora);
  opacity: 0.3;
}

.form-header {
  margin-bottom: var(--space-7);
}

.form-title {
  font-size: var(--text-2xl);
  color: var(--text-primary);
  margin: 0 0 var(--space-3);
  font-weight: var(--font-bold);
  letter-spacing: -0.02em;
}

.form-divider {
  width: 60px;
  height: 2px;
  background: var(--primary-gradient);
  margin-bottom: var(--space-3);
  border-radius: var(--radius-full);
}

.form-subtitle {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin: 0;
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: var(--space-7);
  border-bottom: 1px solid var(--border-base);
}

.login-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.login-tabs :deep(.el-tabs__nav) {
  display: flex;
  gap: var(--space-8);
}

.login-tabs :deep(.el-tabs__item) {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
  padding: 0 var(--space-1) var(--space-3);
  transition: color var(--duration-normal) var(--ease-out);
}

.login-tabs :deep(.el-tabs__item:hover) {
  color: var(--text-secondary);
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
}

.login-tabs :deep(.el-tabs__active-bar) {
  background: var(--primary-gradient);
  height: 2px;
  border-radius: var(--radius-xs);
}

.login-tabs :deep(.el-input__wrapper) {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  box-shadow: none;
  transition: all var(--duration-normal) var(--ease-out);
}

.login-tabs :deep(.el-input__wrapper:hover) {
  border-color: var(--border-hover);
}

.login-tabs :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.login-tabs :deep(.el-input__inner) {
  color: var(--text-primary);
}

.login-tabs :deep(.el-input__prefix .el-icon) {
  color: var(--text-tertiary);
}

.login-tabs :deep(.el-select) {
  width: 100%;
}

.login-tabs :deep(.el-select .el-input) {
  height: 44px;
}

.login-tabs :deep(.el-select .el-input__wrapper) {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
  box-shadow: none !important;
  color: var(--text-primary) !important;
  padding: 0 var(--space-3) !important;
  height: 44px !important;
}

.login-tabs :deep(.el-select .el-input__wrapper:hover) {
  border-color: var(--border-hover) !important;
}

.login-tabs :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px var(--primary-glow) !important;
}

.login-tabs :deep(.el-select .el-input__inner) {
  color: var(--text-primary) !important;
  background: transparent !important;
  height: 44px !important;
  line-height: 44px !important;
}

.login-tabs :deep(.el-select__selected-item) {
  color: var(--text-primary) !important;
}

.login-tabs :deep(.el-select__placeholder) {
  color: var(--text-muted) !important;
}

.login-tabs :deep(.el-select__caret) {
  color: var(--text-tertiary) !important;
}

.login-tabs :deep(.el-select__suffix) {
  color: var(--text-tertiary) !important;
}

.login-tabs :deep(.el-select-dropdown) {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
  box-shadow: var(--shadow-lg) !important;
}

.login-tabs :deep(.el-select-dropdown__item) {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
}

.login-tabs :deep(.el-select-dropdown__item:hover) {
  background: var(--bg-subtle) !important;
  color: var(--text-primary) !important;
}

.login-tabs :deep(.el-select-dropdown__item.is-selected) {
  background: var(--primary-subtle) !important;
  color: var(--primary) !important;
}

.login-tabs :deep(.el-select-dropdown__empty) {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
}

.submit-btn {
  width: 100%;
  border-radius: var(--radius-md);
  height: 44px;
  font-size: var(--text-base);
  font-weight: var(--font-bold);
  background: var(--primary-gradient);
  border: none;
  letter-spacing: 0.1em;
  transition: all var(--duration-normal) var(--ease-spring);
  position: relative;
  overflow: hidden;
}

.btn-bg {
  position: absolute;
  inset: 0;
  background: var(--primary-gradient-hover);
  opacity: 0;
  transition: opacity var(--duration-normal) var(--ease-out);
}

.btn-text {
  position: relative;
  z-index: 1;
  color: #0A0E17;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow);
}

.submit-btn:hover:not(:disabled) .btn-bg {
  opacity: 1;
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.forgot-password-link {
  text-align: center;
  margin-top: var(--space-3);
}

.forgot-password-link a {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  text-decoration: none;
  transition: color var(--duration-fast) var(--ease-out);
}

.forgot-password-link a:hover {
  color: var(--primary);
}

@media (max-width: 768px) {
  .login-left {
    display: none;
  }

  .login-card {
    border-radius: var(--radius-xl);
  }

  .login-right {
    padding: var(--space-6) var(--space-5);
  }
}
</style>

<style>
/* 公告弹窗样式 */
.announcement-dialog .el-dialog {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
}

.announcement-dialog .el-dialog__header {
  border-bottom: 1px solid var(--border-base);
  padding: var(--space-5) var(--space-6);
  margin: 0;
}

.announcement-dialog .el-dialog__title {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.announcement-dialog .el-dialog__body {
  padding: var(--space-6);
}

.announcement-dialog .el-dialog__footer {
  border-top: 1px solid var(--border-base);
  padding: var(--space-4) var(--space-6);
}

.announcement-content p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>

<style>
.login-tabs .el-select-dropdown {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
  box-shadow: var(--shadow-lg) !important;
}

.login-tabs .el-select-dropdown__item {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
}

.login-tabs .el-select-dropdown__item:hover {
  background: var(--bg-subtle) !important;
  color: var(--text-primary) !important;
}

.login-tabs .el-select-dropdown__item.is-selected {
  background: var(--primary-subtle) !important;
  color: var(--primary) !important;
}

.login-tabs .el-select-dropdown__empty {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
}

.el-select-dropdown {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
  box-shadow: var(--shadow-lg) !important;
}

.el-select-dropdown__item {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
}

.el-select-dropdown__item:hover {
  background: var(--bg-subtle) !important;
  color: var(--text-primary) !important;
}

.el-select-dropdown__item.is-selected {
  background: var(--primary-subtle) !important;
  color: var(--primary) !important;
}

.el-select-dropdown__empty {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
}

.el-popper {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
}

.el-popper .el-select-dropdown {
  background: var(--bg-elevated) !important;
}

.login-tabs .el-select .el-input__wrapper,
.el-select .el-input__wrapper {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-base) !important;
  box-shadow: none !important;
}

.login-tabs .el-select .el-input__inner,
.el-select .el-input__inner {
  color: var(--text-primary) !important;
  background: transparent !important;
}

.login-tabs .el-select .el-select__wrapper,
.el-select__wrapper {
  background-color: #0d1421 !important;
}
</style>
