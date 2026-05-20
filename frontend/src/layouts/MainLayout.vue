<template>
  <el-container class="main-layout">
    <div class="aurora-bg">
      <div class="aurora-orb orb-1"></div>
      <div class="aurora-orb orb-2"></div>
      <div class="aurora-orb orb-3"></div>
    </div>
    
    <el-aside :width="sidebarCollapsed ? '0px' : '280px'" class="main-aside">
      <div class="sidebar-inner">
        <div class="aurora-line-top"></div>
        
        <div class="sidebar-header">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <div class="logo-glow"></div>
              <el-icon :size="20"><ChatDotRound /></el-icon>
            </div>
            <div class="logo-text-group">
              <h2 class="logo-text">CampusAsk</h2>
              <span class="logo-subtitle">INTELLIGENT Q&A</span>
            </div>
          </div>
        </div>

        <div class="aurora-divider"></div>

        <button class="new-chat-btn" @click="handleNewChat">
          <div class="btn-bg"></div>
          <el-icon :size="16"><Plus /></el-icon>
          <span>新对话</span>
          <div class="btn-glow"></div>
        </button>

        <div class="chat-history">
          <div class="history-header">
            <span class="history-label">最近对话</span>
            <div class="history-line"></div>
          </div>
          <div
            v-for="session in sessions"
            :key="session.id"
            class="history-item"
            :class="{ active: session.id === activeSessionId }"
            @click="handleSelectSession(session.id)"
          >
            <div class="history-indicator"></div>
            <el-icon :size="14" class="history-icon"><ChatLineSquare /></el-icon>
            <span class="history-title">{{ session.title }}</span>
          </div>
        </div>

        <div class="aurora-divider"></div>

        <div class="sidebar-footer">
          <div
            class="nav-item"
            :class="{ active: activeMenu === 'home' }"
            @click="navigateTo('/')"
          >
            <div class="nav-indicator"></div>
            <el-icon :size="16"><HomeFilled /></el-icon>
            <span>智能问答</span>
          </div>
          <div
            class="nav-item"
            :class="{ active: activeMenu === 'history' }"
            @click="navigateTo('/history')"
          >
            <div class="nav-indicator"></div>
            <el-icon :size="16"><Clock /></el-icon>
            <span>历史记录</span>
          </div>
          <div
            v-if="userStore.isTeacher"
            class="nav-item"
            :class="{ active: activeMenu === 'documents' }"
            @click="navigateTo('/documents')"
          >
            <div class="nav-indicator"></div>
            <el-icon :size="16"><Document /></el-icon>
            <span>文档上传</span>
          </div>
        </div>
      </div>
    </el-aside>

    <el-container class="main-container">
      <el-header class="main-header">
        <div class="header-bg"></div>
        <div class="header-left">
          <button class="toggle-btn" @click="toggleSidebar">
            <el-icon :size="18"><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
          </button>
          <div class="title-group">
            <span class="page-title">{{ pageTitle }}</span>
            <div class="title-line"></div>
          </div>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" popper-class="user-dropdown">
            <div class="user-info">
              <div class="user-avatar">
                <div class="avatar-glow"></div>
                <el-icon :size="15"><UserFilled /></el-icon>
              </div>
              <div class="user-text">
                <span class="username">{{ userStore.user?.username || '同学' }}</span>
                <span class="user-role">{{ userRole }}</span>
              </div>
              <el-icon :size="12" class="dropdown-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="navigateTo('/profile')">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item v-if="userStore.isTeacher" @click="navigateTo('/documents')">
                  <el-icon><Document /></el-icon>
                  我的文档
                </el-dropdown-item>
                <el-dropdown-item v-if="userStore.isAdmin" @click.native="navigateTo('/admin')">
                  <el-icon><Setting /></el-icon>
                  管理后台
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

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
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Plus,
  ChatDotRound,
  ChatLineSquare,
  HomeFilled,
  Clock,
  Fold,
  Expand,
  UserFilled,
  ArrowDown,
  Setting,
  SwitchButton,
  User,
  Document,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { chatApi } from '@/api/chat'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 公告相关
const showAnnouncementDialog = ref(false)
const currentAnnouncement = ref<any>(null)
const announcementsQueue = ref<any[]>([])

onMounted(async () => {
  // 无论是否登录都加载公告
  await loadAnnouncements()
  
  if (sessionStorage.getItem('token')) {
    if (!userStore.user) {
      await userStore.fetchUser()
    }
    await loadSessions()
  }
  window.addEventListener('refresh-sessions', loadSessions)
})

onUnmounted(() => {
  window.removeEventListener('refresh-sessions', loadSessions)
})

const sidebarCollapsed = ref(false)
const sessions = ref<any[]>([])

const userRole = computed(() => {
  if (userStore.isAdmin) return '管理员'
  if (userStore.isTeacher) return '教师'
  return '学生'
})

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/': '智能问答',
    '/history': '历史记录',
    '/admin': '管理后台',
    '/admin/documents': '文档管理',
  }
  return titles[route.path] || '校园问答'
})

const activeMenu = computed(() => {
  if (route.path === '/history') return 'history'
  if (route.path === '/documents') return 'documents'
  return 'home'
})

const activeSessionId = ref<number | null>(null)

const loadSessions = async () => {
  try {
    const res = await chatApi.getSessions()
    sessions.value = res.data
  } catch (error) {
    console.error('加载会话失败:', error)
  }
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const navigateTo = (path: string) => {
  router.push(path)
}

const handleNewChat = async () => {
  activeSessionId.value = null
  router.push('/')
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('clear-chat'))
  }, 100)
  await loadSessions()
  ElMessage.success('已创建新对话')
}

const handleSelectSession = (sessionId: number) => {
  activeSessionId.value = sessionId
  router.push({ path: '/', query: { session: sessionId.toString() } })
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('select-session', { detail: sessionId }))
  }, 50)
}

const handleLogout = async () => {
  await userStore.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
}

// 加载公告
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
</script>

<style scoped>
.main-layout {
  height: 100vh;
  background: var(--bg-base);
  position: relative;
  overflow: hidden;
  width: 100%;
}

.aurora-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.aurora-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
  z-index: 0;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: var(--primary);
  opacity: 0.06;
  top: -200px;
  right: -200px;
  animation: float-slow 12s ease-in-out infinite;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: var(--accent);
  opacity: 0.05;
  bottom: -150px;
  left: -150px;
  animation: float-slow 15s ease-in-out infinite reverse;
}

.orb-3 {
  width: 400px;
  height: 400px;
  background: var(--secondary);
  opacity: 0.04;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: float-slow 18s ease-in-out infinite;
}

@keyframes float-slow {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(30px, -30px); }
}

.sidebar-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-5) 0;
  position: relative;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-base);
  transition: width 0.4s var(--ease-out);
  overflow: hidden;
  z-index: 10;
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

.sidebar-header {
  padding: 0 var(--space-5) var(--space-6);
}

.logo-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: var(--primary-gradient);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0A0E17;
  position: relative;
  transition: all var(--duration-normal) var(--ease-spring);
}

.logo-glow {
  position: absolute;
  inset: -2px;
  background: var(--gradient-aurora);
  border-radius: inherit;
  opacity: 0;
  filter: blur(8px);
  transition: opacity var(--duration-normal) var(--ease-out);
  z-index: -1;
}

.logo-wrapper:hover .logo-icon {
  transform: scale(1.08) rotate(-5deg);
}

.logo-wrapper:hover .logo-glow {
  opacity: 0.5;
}

.logo-text-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.logo-text {
  margin: 0;
  font-size: var(--text-lg);
  color: var(--text-primary);
  font-weight: var(--font-black);
  letter-spacing: -0.03em;
  line-height: 1;
}

.logo-subtitle {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-semibold);
  letter-spacing: 0.15em;
}

.aurora-divider {
  height: 1px;
  margin: 0 var(--space-4);
  background: linear-gradient(90deg, transparent 0%, var(--primary) 50%, transparent 100%);
  opacity: 0.2;
}

.new-chat-btn {
  margin: var(--space-5) var(--space-3) var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--primary-gradient);
  border: none;
  color: #0A0E17;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  transition: all var(--duration-normal) var(--ease-spring);
  width: calc(100% - var(--space-6));
  position: relative;
  overflow: hidden;
  letter-spacing: 0.02em;
}

.btn-bg {
  position: absolute;
  inset: 0;
  background: var(--primary-gradient-hover);
  opacity: 0;
  transition: opacity var(--duration-normal) var(--ease-out);
}

.btn-glow {
  position: absolute;
  inset: -1px;
  background: var(--primary-gradient);
  border-radius: inherit;
  opacity: 0;
  filter: blur(12px);
  transition: opacity var(--duration-normal) var(--ease-out);
  z-index: -1;
}

.new-chat-btn:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--shadow-glow);
}

.new-chat-btn:hover .btn-bg {
  opacity: 1;
}

.new-chat-btn:hover .btn-glow {
  opacity: 0.6;
}

.new-chat-btn:active {
  transform: translateY(0) scale(0.98);
}

.new-chat-btn span,
.new-chat-btn svg {
  position: relative;
  z-index: 1;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-3);
}

.history-header {
  padding: var(--space-2) var(--space-3) var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.history-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-weight: var(--font-bold);
  white-space: nowrap;
}

.history-line {
  flex: 1;
  height: 1px;
  background: var(--border-base);
}

.history-item {
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: 4px;
  position: relative;
  overflow: hidden;
}

.history-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--primary-gradient);
  border-radius: var(--radius-full);
  transition: height var(--duration-normal) var(--ease-spring);
}

.history-item:hover {
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.history-item:hover .history-indicator {
  height: 60%;
}

.history-item.active {
  background: var(--primary-subtle);
  color: var(--primary);
}

.history-item.active .history-indicator {
  height: 70%;
}

.history-icon {
  flex-shrink: 0;
  opacity: 0.6;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.history-item:hover .history-icon,
.history-item.active .history-icon {
  opacity: 1;
}

.history-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.sidebar-footer {
  padding: var(--space-4) var(--space-3);
  border-top: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--primary-gradient);
  border-radius: var(--radius-full);
  transition: height var(--duration-normal) var(--ease-spring);
}

.nav-item:hover {
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.nav-item:hover .nav-indicator {
  height: 50%;
}

.nav-item.active {
  background: var(--primary-subtle);
  color: var(--primary);
}

.nav-item.active .nav-indicator {
  height: 60%;
}

.main-container {
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 5;
  height: 100%;
}

.main-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-base);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  height: 60px;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.header-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0, 229, 160, 0.02) 0%, transparent 100%);
  pointer-events: none;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.toggle-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-tertiary);
  background: transparent;
  border: 1px solid var(--border-base);
  transition: all var(--duration-fast) var(--ease-out);
}

.toggle-btn:hover {
  background: var(--bg-subtle);
  color: var(--primary);
  border-color: var(--border-hover);
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.page-title {
  font-size: var(--text-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.title-line {
  width: 40px;
  height: 2px;
  background: var(--primary-gradient);
  border-radius: var(--radius-full);
  opacity: 0.6;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast) var(--ease-out);
  border: 1px solid transparent;
}

.user-info:hover {
  background: var(--bg-subtle);
  border-color: var(--border-base);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--primary-gradient);
  color: #0A0E17;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.avatar-glow {
  position: absolute;
  inset: -2px;
  background: var(--primary-gradient);
  border-radius: inherit;
  opacity: 0;
  filter: blur(6px);
  transition: opacity var(--duration-normal) var(--ease-out);
  z-index: -1;
}

.user-info:hover .avatar-glow {
  opacity: 0.4;
}

.user-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.username {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: var(--font-semibold);
  line-height: 1;
}

.user-role {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
  line-height: 1;
}

.dropdown-icon {
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) var(--ease-out);
}

.user-info:hover .dropdown-icon {
  color: var(--primary);
}

.main-content {
  padding: 0;
  overflow-y: auto;
  background: transparent;
  display: flex;
  flex-direction: column;
  flex: 1;
  position: relative;
  z-index: 5;
}

.main-content :deep(.home-container) {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.main-content :deep(.history-container) {
  padding: var(--space-6) var(--space-4);
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

/* 公告弹窗样式 */
.announcement-dialog :deep(.el-dialog) {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
}

.announcement-dialog :deep(.el-dialog__header) {
  background: var(--primary-gradient);
  padding: var(--space-5);
}

.announcement-dialog :deep(.el-dialog__title) {
  color: #0A0E17;
  font-weight: var(--font-bold);
}

.announcement-dialog :deep(.el-dialog__body) {
  padding: var(--space-6);
  color: var(--text-primary);
  font-size: var(--text-base);
  line-height: 1.8;
}

.announcement-dialog :deep(.el-dialog__footer) {
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-base);
}

.announcement-content {
  white-space: pre-wrap;
}
</style>
