<template>
  <div class="admin-users">
    <div class="page-content">
      <div class="header-content">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>USER MANAGEMENT</span>
        </div>
        <h2 class="page-title">用户管理</h2>
        <p class="page-desc">管理系统用户和权限设置</p>
        <div class="header-line"></div>
      </div>
      <button class="refresh-btn" @click="loadUsers" :disabled="loading">
        <el-icon :size="14"><Refresh /></el-icon>
        <span>{{ loading ? '刷新中...' : '刷新' }}</span>
      </button>
    </div>

    <div class="content-card">
      <div class="card-glow"></div>
      <el-table :data="users" style="width: 100%" v-loading="loading" class="modern-table" :header-cell-style="{ whiteSpace: 'nowrap' }">
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar-sm">
                <el-icon :size="12"><User /></el-icon>
              </div>
              <span>{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">
            <span class="email-text">{{ row.email || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <span class="role-badge" :class="row.role">{{ getRoleLabel(row.role) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="approval_status" label="审核" width="100">
          <template #default="{ row }">
            <span v-if="row.role === 'teacher'" class="status-badge" :class="row.approval_status">
              {{ getApprovalLabel(row.approval_status) }}
            </span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="max_questions_per_day" label="提问" width="80">
          <template #default="{ row }">
            <span class="count-text">{{ row.max_questions_per_day }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="max_uploads_per_day" label="上传" width="80">
          <template #default="{ row }">
            <span class="count-text">{{ row.max_uploads_per_day }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ban_until" label="封禁状态" min-width="140">
          <template #default="{ row }">
            <span v-if="row.ban_until && new Date(row.ban_until) > new Date()" class="ban-text">
              至 {{ formatDate(row.ban_until) }}
            </span>
            <span v-else class="active-badge">正常</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <template v-if="row.role === 'teacher' && row.pending_approval">
                <button class="action-btn approve-btn" @click="handleApproveUser(row.id)">
                  <el-icon :size="12"><Check /></el-icon>
                  <span>通过</span>
                </button>
                <button class="action-btn reject-btn" @click="handleRejectUser(row.id)">
                  <el-icon :size="12"><Close /></el-icon>
                  <span>驳回</span>
                </button>
              </template>
              <button class="action-btn limit-btn" @click="showLimitDialog(row)">
                <el-icon :size="12"><Setting /></el-icon>
                <span>限制</span>
              </button>
              <button
                v-if="!row.ban_until || new Date(row.ban_until) <= new Date()"
                class="action-btn ban-btn"
                @click="showBanDialog(row)"
              >
                <el-icon :size="12"><Lock /></el-icon>
                <span>封禁</span>
              </button>
              <button
                v-else
                class="action-btn unban-btn"
                @click="handleUnban(row.id)"
              >
                <el-icon :size="12"><Unlock /></el-icon>
                <span>解封</span>
              </button>
              <button
                class="action-btn delete-btn"
                @click="handleDeleteUser(row)"
                :disabled="row.role === 'admin' || row.id === userStore.userId"
              >
                <el-icon :size="12"><Delete /></el-icon>
                <span>删除</span>
              </button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && users.length > 0" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          layout="total, prev, pager, next"
          :total="totalUsers"
          :page-size="pageSize"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <el-dialog v-model="showLimitDialogVisible" title="设置用户限制" width="480px" class="modern-dialog">
      <div class="dialog-form">
        <div class="form-field">
          <label class="field-label">每日提问次数</label>
          <input
            v-model.number="limitForm.max_questions_per_day"
            type="number"
            class="field-input"
            min="0"
            max="1000"
          />
        </div>
        <div class="form-field">
          <label class="field-label">每日上传次数</label>
          <input
            v-model.number="limitForm.max_uploads_per_day"
            type="number"
            class="field-input"
            min="0"
            max="100"
          />
        </div>
        <div class="form-field">
          <label class="field-label">个人信息修改权限</label>
          <div class="checkbox-wrapper">
            <input
              v-model="limitForm.can_modify_profile"
              type="checkbox"
              id="can-modify-profile"
              class="checkbox-input"
            />
            <label for="can-modify-profile" class="checkbox-label">
              允许修改个人信息（包括密码）
            </label>
          </div>
          <p class="field-hint">取消勾选后，用户将无法修改任何个人信息，包括通过重置密码功能</p>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showLimitDialogVisible = false">取消</button>
          <button class="submit-btn" @click="handleLimit" :disabled="limiting">
            <el-icon v-if="limiting" class="is-loading"><Loading /></el-icon>
            <span>{{ limiting ? '保存中...' : '保存' }}</span>
          </button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showBanDialogVisible" title="封禁用户" width="480px" class="modern-dialog">
      <div class="dialog-form">
        <div class="form-field">
          <label class="field-label">封禁时长</label>
          <select v-model.number="banForm.duration" class="field-select">
            <option :value="1">1小时</option>
            <option :value="24">1天</option>
            <option :value="168">7天</option>
            <option :value="720">30天</option>
            <option :value="999999">永久</option>
          </select>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showBanDialogVisible = false">取消</button>
          <button class="submit-btn warning" @click="handleBan" :disabled="banning">
            <el-icon v-if="banning" class="is-loading"><Loading /></el-icon>
            <span>{{ banning ? '封禁中...' : '确认封禁' }}</span>
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, User, Check, Close, Setting, Lock, Unlock, Loading, Delete } from '@element-plus/icons-vue'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { adminApi } from '@/api/admin'

const userStore = useUserStore()
const loading = ref(false)
const limiting = ref(false)
const banning = ref(false)
const users = ref<any[]>([])
const showLimitDialogVisible = ref(false)
const showBanDialogVisible = ref(false)
const currentUserId = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = ref(10)
const totalUsers = ref(0)

const limitForm = reactive({
  max_questions_per_day: 100,
  max_uploads_per_day: 10,
  can_modify_profile: true,
})

const banForm = reactive({
  duration: 24,
})

const getRoleType = (role: string) => {
  const map: Record<string, string> = {
    student: 'success',
    teacher: 'warning',
    admin: 'danger',
  }
  return map[role] || 'info'
}

const getRoleLabel = (role: string) => {
  const map: Record<string, string> = {
    student: '学生',
    teacher: '教师',
    admin: '管理员',
  }
  return map[role] || '未知'
}

const getApprovalType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
  }
  return map[status] || 'info'
}

const getApprovalLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || '未知'
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

const loadUsers = async () => {
  loading.value = true
  try {
    const response = await adminApi.getUsers(currentPage.value, pageSize.value)
    users.value = response.data.items
    totalUsers.value = response.data.total
  } catch (error: any) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadUsers()
}

const handleApproveUser = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要通过该教师注册吗？', '确认通过', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'success',
    })

    await axios.post(
      `/api/v1/admin/users/${id}/approve`,
      {},
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户审核通过')
    await loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.detail || '操作失败，请重试'
      ElMessage.error(msg)
    }
  }
}

const handleRejectUser = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要驳回该教师注册吗？', '确认驳回', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await axios.post(
      `/api/v1/admin/users/${id}/reject`,
      {},
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户审核已驳回')
    await loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.detail || '操作失败，请重试'
      ElMessage.error(msg)
    }
  }
}

const showLimitDialog = (row: any) => {
  currentUserId.value = row.id
  limitForm.max_questions_per_day = row.max_questions_per_day
  limitForm.max_uploads_per_day = row.max_uploads_per_day
  limitForm.can_modify_profile = row.can_modify_profile !== undefined ? row.can_modify_profile : true
  showLimitDialogVisible.value = true
}

const handleLimit = async () => {
  limiting.value = true
  try {
    await axios.put(
      `/api/v1/admin/users/${currentUserId.value}/limit`,
      {
        max_questions_per_day: limitForm.max_questions_per_day,
        max_uploads_per_day: limitForm.max_uploads_per_day,
        can_modify_profile: limitForm.can_modify_profile,
      },
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户限制已更新')
    showLimitDialogVisible.value = false
    await loadUsers()
  } catch (error: any) {
    const msg = error.response?.data?.detail || '操作失败，请重试'
    ElMessage.error(msg)
  } finally {
    limiting.value = false
  }
}

const showBanDialog = (row: any) => {
  currentUserId.value = row.id
  banForm.duration = 24
  showBanDialogVisible.value = true
}

const handleBan = async () => {
  banning.value = true
  try {
    const banUntil = new Date()
    banUntil.setHours(banUntil.getHours() + banForm.duration)

    await axios.post(
      `/api/v1/admin/users/${currentUserId.value}/ban`,
      { ban_until: banUntil.toISOString() },
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户已封禁')
    showBanDialogVisible.value = false
    await loadUsers()
  } catch (error: any) {
    const msg = error.response?.data?.detail || '操作失败，请重试'
    ElMessage.error(msg)
  } finally {
    banning.value = false
  }
}

const handleUnban = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要解封该用户吗？', '确认解封', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'success',
    })

    await axios.post(
      `/api/v1/admin/users/${id}/unban`,
      {},
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户已解封')
    await loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.detail || '操作失败，请重试'
      ElMessage.error(msg)
    }
  }
}

const handleDeleteUser = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${row.username}" 吗？\n\n删除后将无法恢复，包括：\n- 用户上传的所有文档\n- 用户的所有聊天记录\n- 用户的所有会话`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'error',
        dangerouslyUseHTMLString: false,
      }
    )

    await axios.delete(
      `/api/v1/admin/users/${row.id}`,
      { headers: { Authorization: `Bearer ${userStore.token}` } }
    )

    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.detail || '操作失败，请重试'
      ElMessage.error(msg)
    }
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.admin-users {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.page-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-8);
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
  background: rgba(0, 229, 160, 0.08);
  border: 1px solid rgba(0, 229, 160, 0.2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: var(--font-semibold);
  color: var(--primary);
  letter-spacing: 0.1em;
  width: fit-content;
  margin-bottom: var(--space-2);
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

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-4);
  color: var(--text-secondary);
  font-size: var(--text-base);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.refresh-btn:hover:not(:disabled) {
  background: var(--bg-overlay);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.content-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-1);
  overflow: hidden;
  position: relative;
  z-index: 1;
  width: 100%;
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

.modern-table :deep(.el-table) {
  background: transparent;
  color: var(--text-primary);
}

.modern-table :deep(.el-table__header th) {
  background: var(--bg-elevated) !important;
  color: var(--text-primary);
  font-size: var(--text-base);
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

.modern-table :deep(.el-table__empty-block) {
  background: transparent;
}

.modern-table :deep(.el-table__empty-text) {
  color: var(--text-muted);
}

.user-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.user-avatar-sm {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-xs);
  background: var(--primary-subtle);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.email-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.role-badge.student {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.role-badge.teacher {
  background: rgba(245, 158, 11, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.role-badge.admin {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.status-badge.pending {
  background: rgba(245, 158, 11, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.status-badge.approved {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-badge.rejected {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.empty-text {
  color: var(--text-muted);
}

.count-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.ban-text {
  color: var(--accent-light);
  font-size: var(--text-xs);
}

.active-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.action-buttons {
  display: flex;
  gap: var(--space-2);
  flex-wrap: nowrap;
  align-items: center;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: transparent;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xs);
  padding: var(--space-1) var(--space-2);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.action-btn:hover {
  background: var(--bg-subtle);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.approve-btn:hover {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: var(--success);
}

.reject-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--accent);
}

.limit-btn:hover {
  background: var(--primary-subtle);
  border-color: var(--border-focus);
  color: var(--primary);
}

.ban-btn:hover {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.3);
  color: var(--secondary);
}

.unban-btn:hover {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: var(--success);
}

.delete-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--accent);
}

.delete-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.modern-dialog :deep(.el-dialog) {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
}

.modern-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-base);
  padding: var(--space-5) var(--space-6);
  margin: 0;
}

.modern-dialog :deep(.el-dialog__title) {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.modern-dialog :deep(.el-dialog__body) {
  padding: var(--space-6);
}

.modern-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid var(--border-base);
  padding: var(--space-4) var(--space-6);
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.field-input,
.field-select {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-family: inherit;
  outline: none;
  transition: all var(--duration-normal) var(--ease-out);
}

.field-input:focus,
.field-select:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.field-input::placeholder {
  color: var(--text-muted);
}

.field-select {
  cursor: pointer;
}

.field-select option {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.checkbox-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.checkbox-input {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--primary);
}

.checkbox-label {
  font-size: var(--text-sm);
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.field-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.cancel-btn {
  padding: var(--space-2) var(--space-5);
  background: transparent;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.cancel-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  background: var(--primary);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.submit-btn:hover:not(:disabled) {
  background: var(--primary-light);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--primary-glow);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-btn.warning {
  background: var(--secondary);
}

.submit-btn.warning:hover:not(:disabled) {
  background: var(--secondary-light);
  box-shadow: 0 4px 12px var(--secondary-glow);
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: var(--space-5) var(--space-4);
}

.pagination-wrapper :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--text-secondary);
  --el-pagination-button-bg-color: transparent;
  --el-pagination-hover-color: var(--primary);
}

.pagination-wrapper :deep(.el-pagination .btn-prev),
.pagination-wrapper :deep(.el-pagination .btn-next),
.pagination-wrapper :deep(.el-pagination .el-pager li) {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xs);
  color: var(--text-secondary);
  min-width: 32px;
  height: 32px;
  line-height: 32px;
  margin: 0 2px;
}

.pagination-wrapper :deep(.el-pagination .btn-prev:hover),
.pagination-wrapper :deep(.el-pagination .btn-next:hover),
.pagination-wrapper :deep(.el-pagination .el-pager li:hover) {
  background: var(--bg-overlay);
  border-color: var(--primary);
  color: var(--primary);
}

.pagination-wrapper :deep(.el-pagination .el-pager li.is-active) {
  background: var(--primary);
  border-color: var(--primary);
  color: #0A0E17;
  font-weight: var(--font-bold);
}

.pagination-wrapper :deep(.el-pagination .el-pagination__total) {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
</style>
