<template>
  <div class="dashboard-container">
    <div class="page-header">
      <div class="header-badge">
        <div class="badge-dot"></div>
        <span>LIVE DASHBOARD</span>
      </div>
      <h2 class="page-title">数据概览</h2>
      <p class="page-desc">实时监控系统运行状态与关键指标</p>
      <div class="header-line"></div>
    </div>

    <el-row :gutter="24" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card-bg"></div>
          <div class="stat-content">
            <div class="stat-header">
              <div class="stat-icon stat-icon-primary">
                <el-icon :size="24"><ChatLineSquare /></el-icon>
              </div>
              <div class="stat-trend">
                <el-icon><TopRight /></el-icon>
                <span>+12%</span>
              </div>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalQuestions.toLocaleString() }}</div>
              <div class="stat-label">总问答量</div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card-bg"></div>
          <div class="stat-content">
            <div class="stat-header">
              <div class="stat-icon stat-icon-secondary">
                <el-icon :size="24"><Document /></el-icon>
              </div>
              <div class="stat-trend">
                <el-icon><TopRight /></el-icon>
                <span>+8%</span>
              </div>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalDocuments.toLocaleString() }}</div>
              <div class="stat-label">文档总数</div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card-bg"></div>
          <div class="stat-content">
            <div class="stat-header">
              <div class="stat-icon stat-icon-accent">
                <el-icon :size="24"><User /></el-icon>
              </div>
              <div class="stat-trend">
                <el-icon><TopRight /></el-icon>
                <span>+15%</span>
              </div>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalUsers.toLocaleString() }}</div>
              <div class="stat-label">用户总数</div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card-bg"></div>
          <div class="stat-content">
            <div class="stat-header">
              <div class="stat-icon stat-icon-success">
                <el-icon :size="24"><Star /></el-icon>
              </div>
              <div class="stat-trend success">
                <el-icon><CircleCheck /></el-icon>
                <span>{{ stats.satisfaction }}%</span>
              </div>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.satisfaction }}%</div>
              <div class="stat-label">满意度</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="card-glow"></div>
      <div class="card-header">
        <div class="header-left">
          <div class="header-icon-box">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="header-text-group">
            <span class="header-title">热门问题 TOP 10</span>
            <span class="header-subtitle">TOP QUESTIONS</span>
          </div>
        </div>
        <div class="header-badge-small">
          <span>RANKING</span>
        </div>
      </div>
      <div class="card-divider"></div>
      <el-table :data="popularQuestions" style="width: 100%" class="modern-table">
        <el-table-column type="index" label="排名" width="100">
          <template #default="{ $index }">
            <div class="rank-badge" :class="{ 'top-3': $index < 3 }">
              <span class="rank-number">{{ $index + 1 }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题" />
        <el-table-column prop="count" label="提问次数" width="160">
          <template #default="{ row }">
            <div class="count-cell">
              <div class="count-bar" :style="{ width: (row.count / maxQuestionCount * 100) + '%' }"></div>
              <span class="count-value">{{ row.count }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ChatLineSquare, Document, User, Star, TrendCharts, TopRight, CircleCheck } from '@element-plus/icons-vue'
import { adminApi } from '../../api/admin'

const stats = ref({
  totalQuestions: 0,
  totalDocuments: 0,
  totalUsers: 0,
  satisfaction: 0,
})

const popularQuestions = ref<Array<{ question: string; count: number }>>([])

const maxQuestionCount = computed(() => {
  if (popularQuestions.value.length === 0) return 1
  return Math.max(...popularQuestions.value.map((q) => q.count))
})

const loadDashboardData = async () => {
  try {
    const [statsData, questionsData] = await Promise.all([
      adminApi.getStats(),
      adminApi.getPopularQuestions(10),
    ])
    stats.value = statsData
    popularQuestions.value = questionsData
  } catch (error) {
    console.error('加载仪表盘数据失败:', error)
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard-container {
  width: 100%;
  position: relative;
  overflow: hidden;
}

.page-header {
  margin-bottom: var(--space-8);
  position: relative;
  z-index: 1;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: rgba(0, 229, 160, 0.08);
  border: 1px solid rgba(0, 229, 160, 0.2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: var(--font-semibold);
  color: var(--primary);
  letter-spacing: 0.1em;
  margin-bottom: var(--space-3);
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

.page-title {
  font-size: var(--text-3xl);
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
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

.stats-row {
  margin-bottom: var(--space-8);
  position: relative;
  z-index: 1;
}

.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  position: relative;
  overflow: hidden;
  transition: all var(--duration-slow) var(--ease-out);
}

.stat-card-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--primary-subtle) 0%, transparent 50%);
  opacity: 0;
  transition: opacity var(--duration-slow) var(--ease-out);
}

.stat-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-focus);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}

.stat-card:hover .stat-card-bg {
  opacity: 1;
}

.stat-content {
  position: relative;
  z-index: 1;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-4);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-slow) var(--ease-out);
}

.stat-card:hover .stat-icon {
  transform: scale(1.1) rotate(-5deg);
}

.stat-icon-primary {
  background: rgba(0, 229, 160, 0.1);
  color: var(--primary);
  border: 1px solid rgba(0, 229, 160, 0.2);
}

.stat-icon-secondary {
  background: rgba(0, 180, 216, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(0, 180, 216, 0.2);
}

.stat-icon-accent {
  background: rgba(123, 97, 255, 0.1);
  color: var(--accent);
  border: 1px solid rgba(123, 97, 255, 0.2);
}

.stat-icon-success {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  background: rgba(0, 229, 160, 0.08);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--primary);
}

.stat-trend.success {
  background: rgba(16, 185, 129, 0.08);
  color: var(--success);
}

.stat-trend .el-icon {
  font-size: 12px;
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1;
  margin-bottom: var(--space-2);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.content-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  position: relative;
  overflow: hidden;
  z-index: 1;
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-icon-box {
  width: 40px;
  height: 40px;
  background: var(--primary);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all var(--duration-normal) var(--ease-out);
}

.header-icon-box:hover {
  transform: scale(1.05) rotate(-5deg);
  box-shadow: 0 0 20px var(--primary-glow);
}

.header-text-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  line-height: 1.2;
}

.header-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  font-weight: var(--font-medium);
}

.header-badge-small {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.card-divider {
  height: 1px;
  background: linear-gradient(90deg, var(--border-base) 0%, transparent 100%);
  margin-bottom: var(--space-5);
}

.modern-table :deep(.el-table) {
  background: transparent;
  color: var(--text-primary);
}

.modern-table :deep(.el-table__header th) {
  background: var(--bg-elevated) !important;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  border-bottom: 1px solid var(--border-base);
}

.modern-table :deep(.el-table__body td) {
  background: transparent !important;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.modern-table :deep(.el-table__row:hover td) {
  background: var(--bg-subtle) !important;
}

.rank-badge {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  transition: all var(--duration-fast) var(--ease-out);
}

.rank-badge.top-3 {
  background: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 0 12px var(--primary-glow);
}

.rank-number {
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  color: var(--text-secondary);
}

.rank-badge.top-3 .rank-number {
  color: white;
}

.count-cell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}

.count-bar {
  position: absolute;
  right: 0;
  height: 4px;
  background: var(--gradient-aurora);
  border-radius: 2px;
  opacity: 0.3;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.modern-table :deep(.el-table__row:hover) .count-bar {
  opacity: 0.6;
}

.count-value {
  font-weight: var(--font-semibold);
  color: var(--primary);
  font-size: var(--text-sm);
  position: relative;
  z-index: 1;
}
</style>
