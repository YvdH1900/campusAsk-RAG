<template>
  <div class="error-boundary">
    <slot v-if="!hasError" />
    
    <div v-else class="error-container">
      <div class="error-content">
        <div class="error-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        
        <h2 class="error-title">{{ errorTitle }}</h2>
        <p class="error-message">{{ errorMessage }}</p>
        
        <div v-if="showDetails && errorDetails" class="error-details">
          <pre>{{ errorDetails }}</pre>
        </div>
        
        <div class="error-actions">
          <button @click="handleRetry" class="btn-primary">
            {{ retryButtonText }}
          </button>
          <button v-if="canGoBack" @click="goBack" class="btn-secondary">
            返回上页
          </button>
          <button @click="resetError" class="btn-text">
            忽略错误
          </button>
        </div>
        
        <p v-if="supportContact" class="support-info">
          问题持续存在？请联系：<a :href="`mailto:${supportContact}`">{{ supportContact }}</a>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onErrorCaptured, onMounted } from 'vue'
import { useRouter } from 'vue-router'

interface Props {
  fallbackTitle?: string
  fallbackMessage?: string
  showRetry?: boolean
  canGoBack?: boolean
  supportContact?: string
  onError?: (error: Error, instance: any, info: string) => void
  onReset?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  fallbackTitle: '页面出错了',
  fallbackMessage: '抱歉，页面遇到了一些问题',
  showRetry: true,
  canGoBack: true,
  supportContact: '',
  onError: undefined,
  onReset: undefined
})

const emit = defineEmits<{
  error: [error: Error, instance: any, info: string]
  reset: []
  retry: []
}>()

const router = useRouter()

const hasError = ref(false)
const errorInfo = ref<Error | null>(null)
const errorInstance = ref<any>(null)
const errorTrace = ref<string>('')

const errorTitle = computed(() => 
  errorInfo.value?.name || props.fallbackTitle
)

const errorMessage = computed(() => 
  errorInfo.value?.message || props.fallbackMessage
)

const errorDetails = computed(() => {
  if (!errorTrace.value) return null
  
  if (import.meta.env.DEV) {
    return `错误详情:\n${errorTrace.value}\n\n组件实例:\n${JSON.stringify(errorInstance.value, null, 2)}`
  }
  
  return '详细错误信息仅开发环境可见'
})

const showDetails = computed(() => import.meta.env.DEV)

const retryButtonText = computed(() => 
  hasError.value ? '重试' : '重新加载'
)

onErrorCaptured((error: Error, instance: any, info: string) => {
  hasError.value = true
  errorInfo.value = error
  errorInstance.value = instance
  errorTrace.value = info
  
  console.error('🚨 ErrorBoundary 捕获到错误:', {
    error: error.message,
    stack: error.stack,
    component: info,
    instance: instance?.$options?.name || 'Unknown'
  })
  
  emit('error', error, instance, info)
  
  props.onError?.(error, instance, info)
  
  return false
})

function resetError() {
  hasError.value = false
  errorInfo.value = null
  errorInstance.value = null
  errorTrace.value = ''
  
  emit('reset')
  props.onReset?.()
}

function handleRetry() {
  resetError()
  emit('retry')
}

function goBack() {
  router.back()
}
</script>

<style scoped>
.error-boundary {
  width: 100%;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-container {
  max-width: 600px;
  padding: 3rem;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-error, #ef4444);
  box-shadow: var(--shadow-lg);
}

.error-content {
  text-align: center;
}

.error-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 1.5rem;
  color: var(--text-error, #ef4444);
  animation: shake 0.5s ease-in-out;
}

.error-icon svg {
  width: 100%;
  height: 100%;
}

.error-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.75rem;
}

.error-message {
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 1.5rem;
}

.error-details {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  padding: 1rem;
  margin-bottom: 1.5rem;
  text-align: left;
  overflow-x: auto;
}

.error-details pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 1rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
}

.error-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.btn-primary,
.btn-secondary,
.btn-text {
  padding: 0.75rem 1.5rem;
  border-radius: var(--radius-md);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  border: none;
  outline: none;
}

.btn-primary {
  background: var(--primary-gradient);
  color: var(--bg-base);
  box-shadow: var(--shadow-glow-sm);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow-md);
}

.btn-secondary {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border-base);
}

.btn-secondary:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.btn-text {
  background: transparent;
  color: var(--text-tertiary);
}

.btn-text:hover {
  color: var(--text-primary);
}

.support-info {
  font-size: 1rem;
  color: var(--text-tertiary);
}

.support-info a {
  color: var(--primary);
  text-decoration: none;
}

.support-info a:hover {
  text-decoration: underline;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-10px); }
  75% { transform: translateX(10px); }
}

@media (max-width: 640px) {
  .error-container {
    margin: 1rem;
    padding: 2rem;
  }
  
  .error-actions {
    flex-direction: column;
  }
  
  .btn-primary,
  .btn-secondary,
  .btn-text {
    width: 100%;
  }
}
</style>
