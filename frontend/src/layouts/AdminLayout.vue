<template>
  <el-container class="admin-layout">
    <div class="aurora-bg">
      <div class="aurora-orb orb-1"></div>
      <div class="aurora-orb orb-2"></div>
      <div class="aurora-orb orb-3"></div>
    </div>
    
    <el-header class="admin-header">
      <div class="header-left">
        <div class="header-logo">
          <div class="logo-icon">
            <div class="logo-glow"></div>
            <el-icon :size="20"><Setting /></el-icon>
          </div>
          <div class="logo-text-group">
            <h2 class="admin-title">管理后台</h2>
            <span class="admin-subtitle">ADMIN PANEL</span>
          </div>
        </div>
        <div class="admin-badge">
          <div class="badge-dot"></div>
          <span>管理员</span>
        </div>
      </div>
      <div class="header-right">
        <div class="user-info" @click="router.push('/profile')">
          <div class="user-avatar">
            <div class="avatar-glow"></div>
            <el-icon :size="14"><User /></el-icon>
          </div>
          <div class="user-text">
            <span class="username">{{ username }}</span>
            <span class="user-role">管理员</span>
          </div>
        </div>
      </div>
    </el-header>

    <el-container class="admin-container">
      <el-aside width="240px" class="admin-aside">
        <div class="sidebar-header">
          <div class="sidebar-line"></div>
          <span class="sidebar-label">主导航</span>
        </div>
        <nav class="admin-menu">
          <router-link
            to="/admin"
            class="menu-item"
            :class="{ active: route.path === '/admin' }"
          >
            <div class="menu-indicator"></div>
            <el-icon><DataAnalysis /></el-icon>
            <span>数据概览</span>
          </router-link>
          <router-link
            to="/admin/documents"
            class="menu-item"
            :class="{ active: route.path === '/admin/documents' }"
          >
            <div class="menu-indicator"></div>
            <el-icon><Document /></el-icon>
            <span>文档管理</span>
          </router-link>
          <router-link
            to="/admin/upload"
            class="menu-item"
            :class="{ active: route.path === '/admin/upload' }"
          >
            <div class="menu-indicator"></div>
            <el-icon><Upload /></el-icon>
            <span>文档上传</span>
          </router-link>
          <router-link
            to="/admin/users"
            class="menu-item"
            :class="{ active: route.path === '/admin/users' }"
          >
            <div class="menu-indicator"></div>
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </router-link>
          <router-link
            to="/admin/site"
            class="menu-item"
            :class="{ active: route.path === '/admin/site' }"
          >
            <div class="menu-indicator"></div>
            <el-icon><Document /></el-icon>
            <span>网站管理</span>
          </router-link>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="router.push('/')">
            <div class="menu-indicator"></div>
            <el-icon><Back /></el-icon>
            <span>返回主页</span>
          </div>
        </nav>
      </el-aside>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Back, DataAnalysis, Document, Setting, User, Upload } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const username = computed(() => userStore.user?.username || '管理员')
</script>

<style scoped>
.admin-layout {
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

.admin-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-base);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-5);
  height: 64px;
  position: relative;
  z-index: 10;
}

.admin-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--primary) 50%, transparent 100%);
  opacity: 0.3;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.header-logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: var(--primary);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  position: relative;
  transition: all var(--duration-normal) var(--ease-out);
}

.logo-glow {
  position: absolute;
  inset: -4px;
  background: var(--primary);
  border-radius: inherit;
  opacity: 0;
  filter: blur(8px);
  transition: opacity var(--duration-normal) var(--ease-out);
}

.header-logo:hover .logo-icon {
  transform: scale(1.05);
}

.header-logo:hover .logo-glow {
  opacity: 0.4;
}

.logo-text-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.admin-title {
  font-size: var(--text-lg);
  color: var(--text-primary);
  margin: 0;
  font-weight: var(--font-bold);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.admin-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  font-weight: var(--font-medium);
}

.admin-badge {
  background: rgba(0, 229, 160, 0.08);
  border: 1px solid rgba(0, 229, 160, 0.2);
  color: var(--primary);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  cursor: pointer;
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
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.avatar-glow {
  position: absolute;
  inset: -3px;
  background: var(--primary);
  border-radius: inherit;
  opacity: 0;
  filter: blur(6px);
  transition: opacity var(--duration-fast) var(--ease-out);
}

.user-info:hover .avatar-glow {
  opacity: 0.3;
}

.user-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.username {
  font-size: 15px;
  color: var(--text-primary);
  font-weight: var(--font-medium);
  line-height: 17px;
}

.user-role {
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  line-height: 17px;
}

.admin-container {
  height: calc(100vh - 64px);
  position: relative;
  z-index: 5;
  display: flex;
  width: 100%;
}

.admin-aside {
  background: var(--bg-surface);
  border-right: 1px solid var(--border-base);
  padding: var(--space-5) var(--space-3);
  position: relative;
  flex-shrink: 0;
}

.admin-aside::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, var(--primary) 0%, transparent 50%, var(--accent) 100%);
  opacity: 0.15;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3) var(--space-4);
}

.sidebar-line {
  width: 16px;
  height: 2px;
  background: var(--primary);
  border-radius: 1px;
}

.sidebar-label {
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
}

.admin-menu {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-sm);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.menu-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--primary);
  transform: scaleY(0);
  transition: transform var(--duration-fast) var(--ease-out);
  border-radius: 0 2px 2px 0;
}

.menu-item:hover {
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.menu-item:hover::before {
  transform: scaleY(0.5);
}

.menu-item.active {
  background: var(--primary-subtle);
  color: var(--primary);
}

.menu-item.active::before {
  transform: scaleY(1);
}

.menu-indicator {
  width: 4px;
  height: 4px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: all var(--duration-fast) var(--ease-out);
}

.menu-item:hover .menu-indicator {
  background: var(--primary);
  transform: scale(1.5);
}

.menu-item.active .menu-indicator {
  background: var(--primary);
  box-shadow: 0 0 8px var(--primary-glow);
}

.menu-item .el-icon {
  font-size: 18px;
}

.menu-divider {
  height: 1px;
  background: linear-gradient(90deg, var(--border-base) 0%, transparent 100%);
  margin: var(--space-3) var(--space-3);
}

.admin-main {
  padding: var(--space-6) var(--space-4);
  overflow-y: auto;
  background: transparent;
  width: 100%;
  max-width: 100%;
}

.admin-main::-webkit-scrollbar {
  width: 6px;
}

.admin-main::-webkit-scrollbar-track {
  background: transparent;
}

.admin-main::-webkit-scrollbar-thumb {
  background: rgba(0, 229, 160, 0.15);
  border-radius: var(--radius-xs);
}

.admin-main::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 229, 160, 0.25);
}
</style>
