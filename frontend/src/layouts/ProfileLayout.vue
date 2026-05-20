<template>
  <el-container class="profile-layout">
    <div class="aurora-bg">
      <div class="aurora-orb orb-1"></div>
      <div class="aurora-orb orb-2"></div>
      <div class="aurora-orb orb-3"></div>
    </div>
    
    <el-header class="profile-header">
      <div class="header-glow"></div>
      <div class="header-left">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>PROFILE</span>
        </div>
        <div class="header-divider"></div>
        <div class="header-logo">
          <div class="logo-icon">
            <div class="logo-glow"></div>
            <el-icon :size="18"><User /></el-icon>
          </div>
          <h2 class="profile-title">个人资料</h2>
        </div>
      </div>
      <div class="header-right">
        <div class="header-line"></div>
        <button class="back-btn" @click="goBack">
          <el-icon :size="14"><Back /></el-icon>
          <span>返回主页</span>
        </button>
      </div>
    </el-header>

    <el-main class="profile-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { User, Back } from '@element-plus/icons-vue'

const router = useRouter()

const goBack = () => {
  const lastPath = localStorage.getItem('lastPath') || '/'
  router.push(lastPath)
}
</script>

<style scoped>
.profile-layout {
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

.profile-header {
  background: rgba(18, 18, 18, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-base);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-8);
  height: 64px;
  position: relative;
  z-index: 10;
}

.header-glow {
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    var(--primary) 20%, 
    var(--secondary) 50%, 
    var(--primary) 80%, 
    transparent 100%);
  opacity: 0.4;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.header-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--primary-subtle);
  border: 1px solid rgba(0, 229, 160, 0.15);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--primary);
  letter-spacing: 0.05em;
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.header-divider {
  width: 1px;
  height: 24px;
  background: linear-gradient(180deg, transparent, var(--border-base), transparent);
}

.header-logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
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
  transform: scale(1.05) rotate(-5deg);
  box-shadow: 0 0 24px var(--primary-glow);
}

.header-logo:hover .logo-glow {
  opacity: 0.4;
}

.profile-title {
  font-size: var(--text-xl);
  color: var(--text-primary);
  margin: 0;
  font-weight: var(--font-bold);
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.header-line {
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, var(--border-base), transparent);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-base);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.back-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--primary-subtle), transparent);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.back-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 229, 160, 0.15);
}

.back-btn:hover::before {
  opacity: 1;
}

.back-btn:active {
  transform: scale(0.98);
}

.profile-main {
  padding: var(--space-6) var(--space-4);
  overflow-y: auto;
  position: relative;
  z-index: 5;
  background: transparent;
}

.profile-main::-webkit-scrollbar {
  width: 6px;
}

.profile-main::-webkit-scrollbar-track {
  background: transparent;
}

.profile-main::-webkit-scrollbar-thumb {
  background: rgba(0, 229, 160, 0.15);
  border-radius: var(--radius-xs);
}

.profile-main::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 229, 160, 0.3);
}
</style>
