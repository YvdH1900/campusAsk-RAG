<template>
  <div class="forgot-password-container">
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
            <el-icon :size="24"><Lock /></el-icon>
          </div>
          <h1 class="card-title">忘记密码</h1>
          <p class="card-subtitle">输入您的注册邮箱，系统将生成随机密码</p>
        </div>

        <form @submit.prevent="handleSubmit" class="card-form">
          <div class="form-group">
            <label class="form-label">邮箱地址</label>
            <div class="input-wrapper">
              <el-icon class="input-icon"><Message /></el-icon>
              <input
                v-model="email"
                type="email"
                class="form-input"
                placeholder="请输入您的注册邮箱"
                required
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
            <span>{{ loading ? '生成中...' : '生成随机密码' }}</span>
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Message, Loading, ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const email = ref('')
const loading = ref(false)

const handleSubmit = async () => {
  if (!email.value) {
    ElMessage.warning('请输入邮箱地址')
    return
  }

  loading.value = true
  try {
    const response = await axios.post('/api/v1/auth/password-reset/request', {
      email: email.value,
    })

    if (response.data.random_password) {
      // 显示随机密码
      ElMessage.success({
        message: `密码重置成功！随机密码：${response.data.random_password}`,
        duration: 10000,
      })
      // 复制到剪贴板
      navigator.clipboard.writeText(response.data.random_password).then(() => {
        ElMessage.success('密码已复制到剪贴板')
        // 提醒用户尽快修改密码
        ElMessage.warning({
          message: '请尽快修改密码以确保账号安全！',
          duration: 8000,
        })
      })
    } else {
      ElMessage.success(response.data.message || '密码重置成功')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '请求失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.forgot-password-container {
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
