<template>
  <div class="home-container">
    <div v-if="loadingSession" class="welcome-section">
      <div class="welcome-content">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
      </div>
    </div>

    <div v-else-if="messages.length === 0" class="welcome-section">
      <div class="welcome-content">
        <div class="welcome-badge">
          <div class="badge-dot"></div>
          <span>AI POWERED</span>
        </div>
        
        <h1 class="welcome-title">
          <span class="title-line title-line-1">Campus</span>
          <span class="title-line title-line-2 text-gradient">Ask</span>
        </h1>
        
        <div class="title-divider"></div>
        
        <p class="welcome-desc">
          校园知识库智能问答助手<br>
          <span class="desc-sub">解答关于校园生活、学习、管理等方面的疑问</span>
        </p>

        <div class="quick-questions">
          <div class="quick-header">
            <div class="quick-line"></div>
            <span class="quick-title">常见问题</span>
            <div class="quick-line"></div>
          </div>
          <div class="quick-grid">
            <div
              v-for="(question, index) in quickQuestions"
              :key="question"
              class="quick-question-card"
              :style="{ '--delay': `${index * 0.08}s` }"
              @click="handleQuickQuestion(question)"
            >
              <div class="card-number">0{{ index + 1 }}</div>
              <div class="card-content">
                <span>{{ question }}</span>
              </div>
              <div class="card-arrow">
                <el-icon :size="12"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <div class="welcome-stats">
          <div class="stat-item">
            <span class="stat-value">{{ homeStats.totalQuestions }}</span>
            <span class="stat-label">问答次数</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ homeStats.totalDocuments }}</span>
            <span class="stat-label">知识库条目</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ homeStats.satisfaction }}%</span>
            <span class="stat-label">满意度</span>
          </div>
        </div>
      </div>

      <div class="input-section">
        <div class="input-wrapper">
          <textarea
            v-model="inputMessage"
            class="custom-textarea"
            placeholder="输入你的问题..."
            @keydown.enter.exact.prevent="handleSend"
            @input="autoResize"
            ref="textareaRef"
          />
          <button
            class="send-btn"
            :disabled="!inputMessage.trim()"
            @click="handleSend"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </button>
        </div>
        <div class="input-hint">
          <span class="model-badge" v-if="currentModelName">
            <el-icon :size="12"><Cpu /></el-icon>
            {{ currentModelName }}
          </span>
          <span>AI 回答基于校园知识库，仅供参考</span>
        </div>
      </div>
    </div>

    <div v-else class="chat-area">
      <div class="chat-messages" ref="chatMessagesRef">
        <div
          v-for="message in messages"
          :key="message.id"
          class="message-item"
          :class="message.role"
        >
          <div v-if="message.role === 'user'" class="message-row user-row">
            <div class="message-bubble user-bubble">
              {{ message.content }}
            </div>
          </div>

          <div v-else class="message-row assistant-row">
            <div class="message-avatar">
              <el-icon :size="18"><ChatDotRound /></el-icon>
            </div>
            <div class="message-body">
              <div class="message-role-label">AI 助手</div>
              <div v-if="message.content" class="message-bubble assistant-bubble">
                <div class="message-text">{{ message.content }}</div>
              </div>
              <div v-else class="message-bubble assistant-bubble">
                <div class="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>

              <div v-if="message.content && !isLoading" class="message-meta">
                <div v-if="message.sources && message.sources.length > 0" class="message-sources">
                  <div class="sources-title">
                    <el-icon :size="12"><Document /></el-icon>
                    <span>引用来源</span>
                  </div>
                  <div class="source-list">
                    <span
                      v-for="(source, index) in message.sources"
                      :key="index"
                      class="source-tag"
                    >
                      <span class="source-number">{{ index + 1 }}</span>
                      {{ source }}
                    </span>
                  </div>
                </div>

                <div class="message-info-row">
                  <div v-if="message.confidence" class="confidence-badge">
                    <span>置信度</span>
                    <span class="confidence-value" :class="confidenceClass(message.confidence)">{{ message.confidence }}</span>
                  </div>
                  <div v-if="message.features" class="feature-status">
                    <span>重排序</span>
                    <span class="feature-value" :class="rerankMethodClass(message.features.rerank_method)">
                      {{ rerankMethodLabel(message.features.rerank_method) }}
                    </span>
                  </div>
                  <div v-if="message.tokenUsage" class="token-usage">
                    <span>Token: {{ message.tokenUsage.total_tokens }}</span>
                    <span class="token-detail">(输入 {{ message.tokenUsage.input_tokens }} / 输出 {{ message.tokenUsage.output_tokens }})</span>
                  </div>
                  <div v-if="message.verification && !message.verification.is_valid" class="verification-warning">
                    <el-icon :size="14"><WarningFilled /></el-icon>
                    <span>答案可能存在问题</span>
                    <el-tooltip v-if="message.verification.ai_reason" placement="top" :content="message.verification.ai_reason">
                      <el-icon :size="14" class="info-icon"><InfoFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </div>

                <div class="message-feedback">
                  <button
                    class="feedback-btn"
                    :class="{ 'feedback-up-active': message.feedback === 'up' }"
                    @click="handleFeedback(message.id, 'up')"
                  >
                    <el-icon :size="14"><CircleCheck /></el-icon>
                    <span>有帮助</span>
                  </button>
                  <button
                    class="feedback-btn"
                    :class="{ 'feedback-down-active': message.feedback === 'down' }"
                    @click="handleFeedback(message.id, 'down')"
                  >
                    <el-icon :size="14"><CircleClose /></el-icon>
                    <span>需改进</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="input-section">
        <div class="input-wrapper">
          <textarea
            v-model="inputMessage"
            class="custom-textarea"
            placeholder="输入你的问题..."
            :disabled="isLoading"
            @keydown.enter.exact.prevent="handleSend"
            @input="autoResize"
            ref="textareaRef"
          />
          <button
            class="send-btn"
            :disabled="!inputMessage.trim() || isLoading"
            @click="handleSend"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </button>
        </div>
        <div class="input-hint">
          <span class="model-badge" v-if="currentModelName">
            <el-icon :size="12"><Cpu /></el-icon>
            {{ currentModelName }}
          </span>
          <span>AI 回答基于校园知识库，仅供参考</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Document,
  CircleCheck,
  CircleClose,
  Promotion,
  ChatDotRound,
  ArrowRight,
  Cpu,
  WarningFilled,
  InfoFilled,
} from '@element-plus/icons-vue'
import { chatApi } from '../api/chat'

const route = useRoute()
const router = useRouter()
const inputMessage = ref('')
const isLoading = ref(false)
const isInitializing = ref(true)
const textareaRef = ref<HTMLTextAreaElement>()
const chatMessagesRef = ref<HTMLElement>()
const currentSessionId = ref<number | null>(null)
const currentModelName = ref('')

const querySessionId = route.query.session
const initialSessionId = querySessionId ? parseInt(querySessionId as string, 10) : null
const loadingSession = ref(!!initialSessionId)

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  messageId?: number
  confidence?: string
  features?: {
    rerank_method?: string
    reranker_model?: string
  }
  tokenUsage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
  feedback?: 'up' | 'down' | null
  verification?: {
    is_valid: boolean
    confidence: number
    issues: string[]
    ai_reason?: string
  } | null
}

const messages = ref<Message[]>([])

const quickQuestions = ref<string[]>([
  '奖学金申请流程是什么？',
  '图书馆的开放时间是？',
  '如何办理休学手续？',
  '校园网密码忘记了怎么办？',
  '期末考试安排在哪里查询？',
  '如何申请校外住宿？',
])

const homeStats = ref({
  totalQuestions: '0',
  totalDocuments: '0',
  satisfaction: '0',
})

const loadHomeData = async () => {
  try {
    const [statsData, questionsData, modelData] = await Promise.all([
      chatApi.getStats(),
      chatApi.getQuickQuestions(6),
      chatApi.getModelInfo(),
    ])
    const q = statsData.data.totalQuestions
    const d = statsData.data.totalDocuments
    homeStats.value = {
      totalQuestions: q >= 10000 ? `${(q / 10000).toFixed(1)}K+` : q.toString(),
      totalDocuments: d >= 10000 ? `${(d / 10000).toFixed(1)}K+` : d.toString(),
      satisfaction: statsData.data.satisfaction.toString(),
    }
    if (questionsData.data.length > 0) {
      quickQuestions.value = questionsData.data
    }
    currentModelName.value = modelData.data.model_name
  } catch (error) {
    console.error('加载首页数据失败:', error)
  }
}

const loadSessionMessages = async (sessionId: number) => {
  loadingSession.value = true
  try {
    const res = await chatApi.getMessages(sessionId)
    messages.value = res.data.map((msg: any) => ({
      id: msg.id.toString(),
      role: msg.role,
      content: msg.content,
      sources: msg.sources ? (typeof msg.sources === 'string' ? JSON.parse(msg.sources) : msg.sources) : [],
      messageId: msg.id,
      confidence: msg.confidence || null,
      features: msg.features || null,
      tokenUsage: msg.token_usage || null,
      feedback: msg.feedback || null,
    }))
    currentSessionId.value = sessionId
  } catch (error) {
    console.error('加载消息失败:', error)
  } finally {
    loadingSession.value = false
    isInitializing.value = false
  }
}

const clearChat = () => {
  messages.value = []
  inputMessage.value = ''
  currentSessionId.value = null
  isInitializing.value = false
  loadingSession.value = false
  if (route.query.session) {
    router.replace({ query: {} })
  }
}

onMounted(async () => {
  window.addEventListener('clear-chat', clearChat)
  window.addEventListener('select-session', (e: Event) => {
    const sessionId = (e as CustomEvent).detail
    if (sessionId) {
      messages.value = []
      loadSessionMessages(sessionId)
    }
  })
  window.addEventListener('refresh-sessions', () => {
    loadHomeData()
  })

  if (initialSessionId && !isNaN(initialSessionId)) {
    await loadSessionMessages(initialSessionId)
    await loadHomeData()
  } else {
    isInitializing.value = false
    await loadHomeData()
  }

  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = '40px'
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('clear-chat', clearChat)
  window.removeEventListener('refresh-sessions', loadHomeData)
})

watch(
  () => route.query.session,
  async (newSessionId) => {
    if (newSessionId) {
      const sessionId = parseInt(newSessionId as string, 10)
      if (!isNaN(sessionId)) {
        messages.value = []
        await loadSessionMessages(sessionId)
      }
    } else {
      clearChat()
    }
  }
)

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px'
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  })
}

watch(messages, () => {
  scrollToBottom()
}, { deep: true })

const handleSend = async () => {
  const question = inputMessage.value.trim()
  if (!question || isLoading.value) return

  messages.value.push({
    id: Date.now().toString(),
    role: 'user',
    content: question,
  })

  inputMessage.value = ''
  isLoading.value = true

  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }

  const assistantMessageId = (Date.now() + 1).toString()
  messages.value.push({
    id: assistantMessageId,
    role: 'assistant',
    content: '',
    sources: [],
  })

  scrollToBottom()

  chatApi.askStream(
    {
      content: question,
      session_id: currentSessionId.value,
      top_k: 5,
    },
    (chunk: string) => {
      const msg = messages.value.find((m) => m.id === assistantMessageId)
      if (msg) {
        msg.content += chunk
      }
      scrollToBottom()
    },
    (doneData: any) => {
      const msg = messages.value.find((m) => m.id === assistantMessageId)
      if (msg && !msg.messageId) {
        msg.content = doneData.answer
        msg.sources = doneData.sources || []
        msg.messageId = doneData.message_id
        msg.confidence = doneData.confidence
        msg.features = doneData.features
        msg.tokenUsage = doneData.token_usage
      }
      if (doneData.session_id) {
        currentSessionId.value = doneData.session_id
        window.dispatchEvent(new CustomEvent('refresh-sessions'))
      }
      isLoading.value = false
      scrollToBottom()
    },
    (error: string) => {
      const msg = messages.value.find((m) => m.id === assistantMessageId)
      if (msg) {
        msg.content = msg.content || `抱歉，回答失败：${error}`
      }
      isLoading.value = false
      scrollToBottom()
      ElMessage.error('回答生成失败')
    },
    (verificationData: any) => {
      const msg = messages.value.find((m) => m.id === assistantMessageId)
      if (msg) {
        msg.verification = {
          is_valid: verificationData.is_valid,
          confidence: verificationData.confidence,
          issues: verificationData.issues || [],
          ai_reason: verificationData.ai_reason || '',
        }
      }
    }
  )
}

const handleQuickQuestion = (question: string) => {
  inputMessage.value = question
  handleSend()
}

const handleFeedback = async (messageId: string, type: 'up' | 'down') => {
  const msg = messages.value.find((m) => m.id === messageId)
  if (!msg || !msg.messageId) {
    ElMessage.warning('无法提交反馈')
    return
  }

  if (msg.feedback === type) {
    msg.feedback = null
    return
  }

  msg.feedback = type

  try {
    await chatApi.submitFeedback(msg.messageId, { feedback: type })
    if (type === 'up') {
      ElMessage.success('感谢您的反馈！')
    } else {
      ElMessage.info('我们会持续改进')
    }
  } catch (error) {
    msg.feedback = null
    ElMessage.error('反馈提交失败')
  }
}

const confidenceClass = (confidence: string) => {
  if (confidence.includes('高')) return 'confidence-high'
  if (confidence.includes('中')) return 'confidence-medium'
  return 'confidence-low'
}

const rerankMethodClass = (method: string) => {
  if (method === 'api') return 'feature-api'
  if (method === 'heuristic') return 'feature-heuristic'
  return 'feature-unknown'
}

const rerankMethodLabel = (method: string) => {
  if (method === 'api') return 'AI'
  if (method === 'heuristic') return '启发式'
  return '未检测'
}
</script>

<style scoped>
.home-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.welcome-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-base);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.welcome-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 720px;
  width: 100%;
  padding: var(--space-4) var(--space-4) 0;
  overflow-y: auto;
}

.welcome-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  margin-bottom: var(--space-6);
  animation: fadeInDown 0.6s var(--ease-out);
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

.welcome-badge span {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: var(--font-bold);
  letter-spacing: 0.15em;
}

@keyframes fadeInDown {
  from { opacity: 0; transform: translateY(-20px); }
  to { opacity: 1; transform: translateY(0); }
}

.welcome-title {
  font-size: var(--text-hero);
  margin: 0 0 var(--space-4);
  font-weight: var(--font-ultra);
  letter-spacing: -0.04em;
  line-height: 0.9;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.title-line {
  display: block;
  line-height: 1;
}

.title-line-1 {
  color: var(--text-primary);
  transform: skewY(-2deg);
  text-shadow: 4px 4px 0 rgba(0, 229, 160, 0.1);
}

.title-line-2 {
  transform: skewY(2deg) translateX(20px);
}

.title-divider {
  width: 120px;
  height: 4px;
  background: var(--gradient-aurora);
  margin: var(--space-5) auto;
  border-radius: var(--radius-full);
  position: relative;
}

.title-divider::before,
.title-divider::after {
  content: '';
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
}

.title-divider::before { left: -16px; }
.title-divider::after { right: -16px; }

.welcome-desc {
  font-size: var(--text-lg);
  color: var(--text-secondary);
  margin: 0 0 var(--space-10);
  line-height: var(--leading-relaxed);
  font-weight: var(--font-medium);
}

.desc-sub {
  font-size: var(--text-base);
  color: var(--text-tertiary);
  font-weight: var(--font-normal);
}

.quick-questions {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-2xl);
  padding: var(--space-4);
  position: relative;
  overflow-y: auto;
  margin-bottom: var(--space-6);
  width: 100%;
  max-height: 340px;
}

.quick-questions::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--gradient-aurora);
  opacity: 0.6;
}

.quick-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.quick-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--border-base) 50%, transparent 100%);
}

.quick-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  white-space: nowrap;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
  overflow-y: visible;
  padding-right: 0;
}

.quick-grid::-webkit-scrollbar {
  width: 4px;
}

.quick-grid::-webkit-scrollbar-track {
  background: var(--bg-elevated);
  border-radius: 2px;
}

.quick-grid::-webkit-scrollbar-thumb {
  background: var(--border-base);
  border-radius: 2px;
}

.quick-grid::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.quick-question-card {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-spring);
  text-align: left;
  position: relative;
  overflow: hidden;
  animation: fadeInUp 0.5s var(--ease-out) both;
  animation-delay: var(--delay, 0s);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.card-number {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-bold);
  letter-spacing: 0.1em;
  opacity: 0.5;
}

.card-content { flex: 1; }

.card-content span {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-snug);
  font-weight: var(--font-medium);
  position: relative;
  z-index: 1;
}

.card-arrow {
  position: absolute;
  bottom: var(--space-3);
  right: var(--space-3);
  color: var(--text-muted);
  opacity: 0;
  transform: translateX(-8px);
  transition: all var(--duration-normal) var(--ease-out);
}

.quick-question-card:hover {
  background: var(--bg-overlay);
  border-color: var(--border-hover);
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
}

.quick-question-card:hover .card-content span { color: var(--text-primary); }
.quick-question-card:hover .card-arrow { opacity: 1; transform: translateX(0); color: var(--primary); }
.quick-question-card:active { transform: translateY(-2px); }

.welcome-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  width: 100%;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-black);
  background: var(--gradient-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: var(--border-base);
}

.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 0 var(--space-4);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) 0;
  scroll-behavior: smooth;
}

.chat-messages::-webkit-scrollbar {
  width: 4px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--border-base);
  border-radius: var(--radius-full);
}

.message-item {
  margin-bottom: var(--space-6);
  animation: slideUp 0.3s var(--ease-out);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.user-row {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.assistant-row {
  justify-content: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--primary-gradient);
  color: #0A0E17;
}

.message-body {
  flex: 1;
  min-width: 0;
  max-width: 85%;
}

.user-row .message-body {
  display: flex;
  flex-direction: row-reverse;
}

.message-role-label {
  font-size: var(--text-xs);
  color: var(--primary);
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: var(--space-2);
}

.message-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-xl);
  line-height: var(--leading-relaxed);
  font-size: var(--text-base);
  word-break: break-word;
}

.user-bubble {
  background: var(--primary-gradient);
  color: #0A0E17;
  border-bottom-right-radius: var(--radius-sm);
  font-weight: var(--font-medium);
  max-width: 70%;
  margin-left: auto;
}

.assistant-bubble {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-bottom-left-radius: var(--radius-sm);
  border: 1px solid var(--border-base);
}

.message-sources {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}

.message-meta {
  margin-top: var(--space-3);
}

.message-info-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
  flex-wrap: wrap;
}

.confidence-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.confidence-value {
  font-weight: var(--font-bold);
}

.confidence-high {
  color: #10b981;
}

.confidence-medium {
  color: #f59e0b;
}

.confidence-low {
  color: #ef4444;
}

.feature-status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.feature-value {
  font-weight: var(--font-bold);
}

.feature-api {
  color: #10b981;
}

.feature-heuristic {
  color: #f59e0b;
}

.feature-unknown {
  color: #9ca3af;
}

.token-usage {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.token-detail {
  color: var(--text-muted);
  opacity: 0.7;
}

.verification-warning {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: #ef4444;
}

.verification-warning .info-icon {
  cursor: help;
  opacity: 0.7;
}

.verification-warning .info-icon:hover {
  opacity: 1;
}

.sources-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-bold);
  margin-bottom: var(--space-2);
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.source-number {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #0A0E17;
  border-radius: 50%;
  font-size: 12px;
  font-weight: var(--font-bold);
}

.message-feedback {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.feedback-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  outline: none;
}

.feedback-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.feedback-btn:active {
  transform: scale(0.96);
}

.feedback-up-active {
  background: rgba(0, 229, 160, 0.12) !important;
  border-color: var(--primary) !important;
  color: var(--primary) !important;
}

.feedback-down-active {
  background: rgba(255, 107, 107, 0.12) !important;
  border-color: var(--danger) !important;
  color: var(--danger) !important;
}

.loading-dots {
  display: flex;
  gap: 6px;
  padding: var(--space-2) 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
  animation: loadingBounce 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.16s; }
.loading-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes loadingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.input-section {
  padding: var(--space-4) 0 var(--space-6);
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  width: 100%;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-3) var(--space-4);
  transition: all var(--duration-normal) var(--ease-out);
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
  min-height: 56px;
}

.input-wrapper:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.custom-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: var(--text-base);
  font-family: inherit;
  resize: none;
  min-height: 40px;
  max-height: 120px;
  line-height: var(--leading-relaxed);
  padding: 0;
}

.custom-textarea::placeholder { color: var(--text-tertiary); }
.custom-textarea:disabled { opacity: 0.5; }

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: var(--primary-gradient);
  border: none;
  color: #0A0E17;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--duration-normal) var(--ease-spring);
  outline: none;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 20px var(--primary-glow);
}

.send-btn:active:not(:disabled) { transform: translateY(0) scale(0.95); }
.send-btn:disabled { background: var(--bg-elevated); color: var(--text-muted); cursor: not-allowed; box-shadow: none; }

.input-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  font-weight: var(--font-medium);
}

.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  background: rgba(0, 229, 160, 0.08);
  border: 1px solid rgba(0, 229, 160, 0.2);
  border-radius: var(--radius-full);
  color: var(--primary);
  font-weight: var(--font-semibold);
  font-size: 11px;
}

@media (max-width: 768px) {
  .chat-area { padding: 0 var(--space-3); }
  .quick-grid { grid-template-columns: repeat(2, 1fr); }
  .message-bubble { max-width: 90% !important; }
  .welcome-title { font-size: var(--text-4xl); }
  .welcome-stats { flex-direction: column; gap: var(--space-3); }
  .input-wrapper { margin: 0 var(--space-2); }
}
</style>
