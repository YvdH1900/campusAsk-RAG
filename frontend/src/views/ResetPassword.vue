<template>
  <div class="reset-password-container">
    <div class="aurora-bg">
      <div class="aurora-orb orb-1"></div>
      <div class="aurora-orb orb-2"></div>
    </div>

    <div class="card-wrapper">
      <div class="auth-card">
        <div class="card-glow"></div>
        <div class="aurora-line-top"></div>

        <div class="card-header">
          <div class="logo-icon">
            <el-icon :size="24"><Key /></el-icon>
          </div>
          <h1 class="card-title">重置密码</h1>
          <p class="card-subtitle">请输入您的新密码</p>
        </div>

        <form @submit.prevent="handleSubmit" class="card-form">
          <div class="form-group">
            <label class="form-label">新密码</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <input
                v-model="newPassword"
                type="password"
                class="form-input"
                placeholder="请输入新密码（至少6位）"
                required
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">确认密码</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <input
                v-model="confirmPassword"
                type="password"
                class="form-input"
                placeholder="请再次输入新密码"
                required
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
            <span>{{ loading ? '重置中...' : '重置密码' }}</span>
          </button>
        </form>

        <div class="card-footer">
          <router-link to="/login" class="back-link">
            <el-icon :size="14"><ArrowLeft /></el-icon>
            <span>返回登录</span>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Key, Lock, Loading, ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

onMounted(() => {
  const queryToken = route.query.token as string
  if (queryToken) {
    token.value = queryToken
  } else {
    ElMessage.error('缺少重置令牌')
    router.push('/forgot-password')
  }
})

const handleSubmit = async () => {
  if (!newPassword.value || !confirmPassword.value) {
    ElMessage.warning('请填写所有字段')
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  if (newPassword.value.length < 6) {
    ElMessage.warning('密码长度不能少于 6 位')
    return
  }

  loading.value = true
  try {
    await axios.post('/api/v1/auth/password-reset/confirm', {
      token: token.value,
      new_password: newPassword.value,
    })

    ElMessage.success('密码重置成功，请使用新密码登录')
    router.push('/login')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '重置失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.reset-password-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-base);
  position: relative;
  overflow: hidden;
}

.aurora-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.aurora-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: var(--primary);
  opacity: 0.06;
  top: -150px;
  right: -150px;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: var(--accent);
  opacity: 0.05;
  bottom: -100px;
  left: -100px;
}

.card-wrapper {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  padding: var(--space-4);
}

.auth-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-8);
  position: relative;
  overflow: hidden;
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

.aurora-line-top {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--gradient-aurora);
  opacity: 0.6;
}

.card-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.logo-icon {
  width: 56px;
  height: 56px;
  background: var(--primary-gradient);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0A0E17;
  margin: 0 auto var(--space-4);
}

.card-title {
  font-size: var(--text-2xl);
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
  font-weight: var(--font-bold);
}

.card-subtitle {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

.card-form {
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
}

.form-input {
  width: 100%;
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4) var(--space-3) var(--space-10);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: all var(--duration-normal) var(--ease-out);
}

.form-input:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--primary-gradient);
  border: none;
  border-radius: var(--radius-sm);
  color: #0A0E17;
  font-size: var(--text-base);
  font-weight: var(--font-bold);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  margin-top: var(--space-2);
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.card-footer {
  margin-top: var(--space-6);
  text-align: center;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  text-decoration: none;
  transition: color var(--duration-fast) var(--ease-out);
}

.back-link:hover {
  color: var(--primary);
}
</style>
