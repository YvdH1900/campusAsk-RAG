<template>
  <div class="history-container">
    <div class="page-content">
      <div class="header-content">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>CHAT HISTORY</span>
        </div>
        <h2 class="page-title">历史记录</h2>
        <p class="page-desc">查看和管理你的对话历史</p>
        <div class="header-line"></div>
      </div>
    </div>

    <div class="search-wrapper">
      <div class="search-input-container">
        <el-icon class="search-icon"><Search /></el-icon>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索历史记录..."
        />
        <button
          v-if="searchQuery"
          class="clear-btn"
          @click="searchQuery = ''"
        >
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </div>

    <div class="history-list">
      <div
        v-for="session in filteredSessions"
        :key="session.id"
        class="session-card"
      >
        <div class="card-glow"></div>
        <div class="session-content">
          <div class="session-icon">
            <el-icon><ChatLineSquare /></el-icon>
          </div>
          <div class="session-main" @click="handleOpenSession(session.id)">
            <div class="session-header">
              <h3 class="session-title">{{ session.title }}</h3>
              <span class="session-time">{{ session.updatedAt }}</span>
            </div>
            <p class="session-preview">{{ session.preview }}</p>
            <div class="session-meta">
              <span class="meta-tag">{{ session.messageCount }} 条对话</span>
            </div>
          </div>
          <div class="session-actions">
            <button
              class="delete-btn"
              @click.stop="handleDelete(session.id)"
            >
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <div v-if="filteredSessions.length === 0" class="empty-state">
        <div class="empty-icon">
          <el-icon :size="56"><ChatLineSquare /></el-icon>
        </div>
        <p class="empty-text">暂无历史记录</p>
        <p class="empty-hint">开始你的第一次对话吧</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, ChatLineSquare, Close, Clock } from '@element-plus/icons-vue'
import { chatApi } from '@/api/chat'

const router = useRouter()

const searchQuery = ref('')
const loading = ref(false)

interface Session {
  id: number
  title: string
  preview: string
  updatedAt: string
  messageCount: number
}

const sessions = ref<Session[]>([])

onMounted(async () => {
  await loadSessions()
})

const loadSessions = async () => {
  loading.value = true
  try {
    const res = await chatApi.getSessions()
    sessions.value = res.data.map((s: any) => ({
      id: s.id,
      title: s.title || '新对话',
      preview: '',
      updatedAt: formatTime(s.updated_at),
      messageCount: s.message_count || 0,
    }))
  } catch (error) {
    console.error('加载历史记录失败:', error)
    ElMessage.error('加载历史记录失败')
  } finally {
    loading.value = false
  }
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  const d = new Date(timeStr + 'Z')
  return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

const filteredSessions = computed(() => {
  if (!searchQuery.value) return sessions.value
  return sessions.value.filter(session =>
    session.title.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
    session.preview.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const handleOpenSession = (sessionId: number) => {
  router.push({ path: '/', query: { session: sessionId.toString() } })
}

const handleDelete = async (sessionId: number) => {
  ElMessageBox.confirm('确定要删除这条历史记录吗？', '确认删除', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await chatApi.deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      window.dispatchEvent(new CustomEvent('refresh-sessions'))
      ElMessage.success('删除成功')
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}
</script>

<style scoped>
.history-container {
  position: relative;
  overflow: visible;
  min-height: 100%;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  z-index: 10;
  pointer-events: auto;
}

.page-content {
  margin-bottom: var(--space-6);
  position: relative;
  z-index: 1;
  width: 100%;
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

.search-wrapper {
  margin-bottom: var(--space-6);
  position: relative;
  z-index: 15;
  width: 100%;
  pointer-events: auto;
}

.search-input-container {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-4);
  transition: all var(--duration-normal) var(--ease-out);
  pointer-events: auto;
  cursor: text;
}

.search-input-container:focus-within {
  border-color: var(--primary);
  background: var(--bg-elevated);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.search-icon {
  color: var(--text-tertiary);
  margin-right: var(--space-3);
  font-size: var(--text-lg);
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: var(--text-base);
  font-family: inherit;
  pointer-events: auto;
  cursor: text;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.clear-btn {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xs);
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.clear-btn:hover {
  background: var(--bg-overlay);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  position: relative;
  z-index: 10;
  width: 100%;
  pointer-events: auto;
}

.session-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  transition: all var(--duration-slow) var(--ease-out);
  position: relative;
  overflow: visible;
  animation: fadeInUp 0.4s var(--ease-out) both;
  pointer-events: auto;
  z-index: 5;
  width: 100%;
  box-sizing: border-box;
}

.session-card:nth-child(1) { animation-delay: 0.05s; }
.session-card:nth-child(2) { animation-delay: 0.1s; }
.session-card:nth-child(3) { animation-delay: 0.15s; }
.session-card:nth-child(4) { animation-delay: 0.2s; }
.session-card:nth-child(5) { animation-delay: 0.25s; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--primary) 50%, transparent 100%);
  opacity: 0;
  transition: opacity var(--duration-normal) var(--ease-out);
  pointer-events: none;
}

.session-card:hover .card-glow {
  opacity: 0.3;
}

.session-card:hover {
  transform: translateY(-2px);
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}

.session-content {
  display: flex;
  flex-direction: row;
  gap: var(--space-4);
  align-items: flex-start;
  width: 100%;
  position: relative;
  z-index: 10;
}

.session-icon {
  width: 44px;
  height: 44px;
  min-width: 44px;
  max-width: 44px;
  flex-shrink: 0;
  flex-grow: 0;
  background: var(--primary-subtle);
  border: 1px solid var(--border-focus);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  transition: all var(--duration-normal) var(--ease-out);
  overflow: hidden;
}

.session-icon :deep(.el-icon) {
  width: 20px;
  height: 20px;
  font-size: 20px;
  flex-shrink: 0;
}

.session-card:hover .session-icon {
  background: var(--primary);
  color: white;
  transform: scale(1.05);
  box-shadow: 0 0 20px var(--primary-glow);
}

.session-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
  position: relative;
  z-index: 10;
}

.session-header {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
  gap: var(--space-3);
}

.session-title {
  font-size: var(--text-base);
  color: #FFFFFF;
  margin: 0;
  font-weight: var(--font-semibold);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: var(--text-xs);
  color: #6B7F99;
  white-space: nowrap;
  flex-shrink: 0;
}

.session-preview {
  font-size: var(--text-sm);
  color: #B8C5D6;
  margin: 0 0 var(--space-2);
  white-space: pre-line;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: var(--leading-relaxed);
}

.session-meta {
  display: flex;
  flex-direction: row;
  gap: var(--space-2);
  align-items: center;
}

.meta-tag {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--bg-elevated);
  padding: 4px 12px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-base);
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  white-space: nowrap;
}

.session-actions {
  flex-shrink: 0;
  padding-top: var(--space-1);
  display: flex;
  align-items: center;
}

.delete-btn {
  background: transparent;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  opacity: 0;
}

.session-card:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--accent);
}

.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-5);
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.empty-text {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0 0 var(--space-2);
}

.empty-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}
</style>
