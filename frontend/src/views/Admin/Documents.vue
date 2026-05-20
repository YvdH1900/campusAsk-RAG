<template>
  <div class="documents-container">
    <div class="page-content">
      <div class="header-content">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>DOCUMENT MANAGEMENT</span>
        </div>
        <h2 class="page-title">文档管理</h2>
        <p class="page-desc">管理知识库文档，支持搜索、筛选和删除</p>
        <div class="header-line"></div>
      </div>
      <div class="header-actions">
        <div class="search-input-wrapper">
          <el-icon class="search-icon"><Search /></el-icon>
          <input
            v-model="searchQuery"
            type="text"
            class="search-input"
            placeholder="搜索文档..."
          />
        </div>
        <select v-model="filterStatus" class="filter-select">
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="processing">处理中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
        </select>
        <button class="refresh-btn" @click="loadDocuments" :disabled="loading">
          <el-icon :class="{ 'is-loading': loading }"><Refresh /></el-icon>
          <span>刷新</span>
        </button>
      </div>

      <div v-if="selectedDocuments.length > 0" class="batch-actions">
        <span class="selected-count">已选择 {{ selectedDocuments.length }} 项</span>
        <button class="batch-btn approve-batch-btn" @click="handleBatchApprove">
          <el-icon><Check /></el-icon>
          <span>批量通过</span>
        </button>
        <button class="batch-btn reject-batch-btn" @click="handleBatchReject">
          <el-icon><Close /></el-icon>
          <span>批量驳回</span>
        </button>
        <button class="batch-btn delete-batch-btn" @click="handleBatchDelete">
          <el-icon><Delete /></el-icon>
          <span>批量删除</span>
        </button>
        <button class="batch-btn clear-selection-btn" @click="clearSelection">
          <span>取消选择</span>
        </button>
      </div>
    </div>

    <div class="content-card">
      <div class="card-glow"></div>
      <div v-if="loading" class="loading-wrapper">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <el-table
        v-else
        :data="documents"
        style="width: 100%"
        class="modern-table"
        empty-text="暂无文档数据"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="file-name-cell">
              <el-icon class="file-icon"><Document /></el-icon>
              <span>{{ row.filename }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <span class="category-tag">{{ row.category || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="处理状态" width="120">
          <template #default="{ row }">
            <span class="status-tag" :class="row.status">
              {{ getStatusText(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="review_status" label="审核状态" width="120">
          <template #default="{ row }">
            <span class="status-tag" :class="'review-' + row.review_status">
              {{ getReviewStatusText(row.review_status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="文件大小" width="100">
          <template #default="{ row }">
            <span class="file-size">{{ formatFileSize(row.file_size) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="150">
          <template #default="{ row }">
            <span class="detail-text" :class="getDetailClass(row)">
              {{ getDetailText(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            <span class="date-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <button
                v-if="row.review_status === 'pending'"
                class="action-btn approve-btn"
                @click="handleApprove(row)"
              >
                <el-icon><Check /></el-icon>
                <span>通过</span>
              </button>
              <button
                v-if="row.review_status === 'pending'"
                class="action-btn reject-btn"
                @click="handleReject(row)"
              >
                <el-icon><Close /></el-icon>
                <span>驳回</span>
              </button>
              <button
                v-if="row.review_status !== 'rejected'"
                class="action-btn preview-btn"
                @click="handlePreview(row)"
              >
                <el-icon><View /></el-icon>
                <span>预览</span>
              </button>
              <button
                v-if="row.review_status !== 'rejected'"
                class="action-btn download-btn"
                @click="handleDownload(row)"
              >
                <el-icon><Download /></el-icon>
                <span>下载</span>
              </button>
              <button class="action-btn delete-btn" @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
                <span>删除</span>
              </button>
              <span v-if="row.review_status === 'rejected'" class="empty-text">文件已删除</span>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && documents.length > 0" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          layout="total, prev, pager, next"
          :total="totalDocuments"
          :page-size="pageSize"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Document, Delete, Refresh, Loading, Check, Close, View, Download } from '@element-plus/icons-vue'
import { getAllDocuments, getPendingDocuments, reviewDocument, deleteDocument, batchDeleteDocuments, batchReviewDocuments, downloadDocument, previewDocument, type DocumentResponse } from '@/api/documents'

const searchQuery = ref('')
const filterStatus = ref('')
const documents = ref<DocumentResponse[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const totalDocuments = ref(0)
const selectedDocuments = ref<DocumentResponse[]>([])

const handleSelectionChange = (selection: DocumentResponse[]) => {
  selectedDocuments.value = selection
}

const clearSelection = () => {
  selectedDocuments.value = []
}

const loadDocuments = async () => {
  loading.value = true
  try {
    const res = await getAllDocuments(currentPage.value, pageSize.value, filterStatus.value || undefined)
    documents.value = res.data.items
    totalDocuments.value = res.data.total
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载文档列表失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadDocuments()
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return texts[status] || status
}

const getReviewStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
  }
  return texts[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-')
}

const formatFileSize = (bytes: number) => {
  if (!bytes || bytes === 0) return '-'
  const kb = bytes / 1024
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`
  }
  const mb = kb / 1024
  return `${mb.toFixed(2)} MB`
}

const getDetailText = (row: DocumentResponse) => {
  // 如果是驳回状态，显示驳回理由
  if (row.review_status === 'rejected') {
    return row.reject_reason || '已驳回'
  }
  // 如果是失败状态，显示失败原因
  if (row.status === 'failed') {
    return '处理失败'
  }
  // 其他状态显示默认
  return '-'
}

const getDetailClass = (row: DocumentResponse) => {
  if (row.review_status === 'rejected') {
    return 'detail-rejected'
  }
  if (row.status === 'failed') {
    return 'detail-failed'
  }
  return ''
}

const handleDelete = (doc: DocumentResponse) => {
  ElMessageBox.confirm(
    `确定要删除文档 "${doc.filename}" 吗？此操作将同时删除本地文件、向量库数据和数据库记录，不可恢复。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    }
  ).then(async () => {
    try {
      await deleteDocument(doc.id)
      ElMessage.success('删除成功')
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }).catch(() => {})
}

const handleApprove = (doc: DocumentResponse) => {
  ElMessageBox.confirm(
    `确定要通过文档 "${doc.filename}" 吗？通过后将自动处理并加入知识库。`,
    '确认通过',
    {
      confirmButtonText: '确定通过',
      cancelButtonText: '取消',
      type: 'success',
    }
  ).then(async () => {
    try {
      await reviewDocument(doc.id, { action: 'approve' })
      ElMessage.success('审核通过，文档正在处理中')
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '审核失败')
    }
  }).catch(() => {})
}

const handleReject = (doc: DocumentResponse) => {
  ElMessageBox.prompt(
    `请输入驳回 "${doc.filename}" 的理由：`,
    '驳回文档',
    {
      confirmButtonText: '确认驳回',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '驳回理由不能为空',
      inputType: 'textarea',
    }
  ).then(async ({ value }) => {
    try {
      await reviewDocument(doc.id, { action: 'reject', reason: value })
      ElMessage.warning('已驳回文档')
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '驳回失败')
    }
  }).catch(() => {})
}

const handleBatchDelete = () => {
  const ids = selectedDocuments.value.map(d => d.id)
  ElMessageBox.confirm(
    `确定要删除选中的 ${ids.length} 个文档吗？此操作将同时删除本地文件、向量库数据和数据库记录，不可恢复。`,
    '批量删除确认',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    }
  ).then(async () => {
    try {
      const res = await batchDeleteDocuments(ids)
      ElMessage.success(res.data.message)
      clearSelection()
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '批量删除失败')
    }
  }).catch(() => {})
}

const handleBatchApprove = () => {
  const pendingDocs = selectedDocuments.value.filter(d => d.review_status === 'pending')
  if (pendingDocs.length === 0) {
    ElMessage.warning('请选择待审核的文档')
    return
  }
  const ids = pendingDocs.map(d => d.id)
  ElMessageBox.confirm(
    `确定要通过选中的 ${ids.length} 个文档吗？通过后将自动处理并加入知识库。`,
    '批量通过确认',
    {
      confirmButtonText: '确定通过',
      cancelButtonText: '取消',
      type: 'success',
    }
  ).then(async () => {
    try {
      const res = await batchReviewDocuments(ids, 'approve')
      ElMessage.success(res.data.message)
      clearSelection()
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '批量通过失败')
    }
  }).catch(() => {})
}

const handleBatchReject = () => {
  const pendingDocs = selectedDocuments.value.filter(d => d.review_status === 'pending')
  if (pendingDocs.length === 0) {
    ElMessage.warning('请选择待审核的文档')
    return
  }
  const ids = pendingDocs.map(d => d.id)
  ElMessageBox.prompt(
    `请输入批量驳回 ${ids.length} 个文档的理由：`,
    '批量驳回',
    {
      confirmButtonText: '确认驳回',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '驳回理由不能为空',
      inputType: 'textarea',
    }
  ).then(async ({ value }) => {
    try {
      const res = await batchReviewDocuments(ids, 'reject', value)
      ElMessage.warning(res.data.message)
      clearSelection()
      await loadDocuments()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '批量驳回失败')
    }
  }).catch(() => {})
}

const handleDownload = (doc: DocumentResponse) => {
  if (doc.review_status === 'rejected') {
    ElMessage.warning('已驳回的文档文件已被删除，无法下载')
    return
  }
  downloadDocument(doc.id)
  ElMessage.success('开始下载文档')
}

const handlePreview = async (doc: DocumentResponse) => {
  if (doc.review_status === 'rejected') {
    ElMessage.warning('已驳回的文档文件已被删除，无法预览')
    return
  }
  try {
    const response = await previewDocument(doc.id)
    ElMessageBox.alert(
      `<pre style="white-space: pre-wrap; word-break: break-all; max-height: 60vh; overflow-y: auto; font-size: 14px; line-height: 1.6;">${response.data.content}</pre>`,
      `预览: ${response.data.filename}`,
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '关闭',
        customClass: 'preview-dialog',
      }
    )
  } catch (error: any) {
    const msg = error.response?.data?.detail || '预览失败'
    if (msg.includes('不支持预览')) {
      ElMessage.warning(msg)
    } else {
      ElMessage.error(msg)
    }
  }
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.documents-container {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  width: 100%;
  max-width: 1400px;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-3);
  color: var(--text-tertiary);
  font-size: var(--text-base);
  pointer-events: none;
}

.search-input {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4) var(--space-3) var(--space-10);
  color: var(--text-primary);
  font-size: var(--text-sm);
  width: 280px;
  outline: none;
  transition: all var(--duration-normal) var(--ease-out);
  -webkit-text-fill-color: var(--text-primary);
}

.search-input:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.search-input::placeholder {
  color: var(--text-tertiary);
}

.filter-select {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.filter-select:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
}

.filter-select option {
  background: var(--bg-elevated);
  color: var(--text-primary);
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

.batch-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
}

.selected-count {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.batch-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-xs);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.approve-batch-btn {
  background: rgba(0, 229, 160, 0.1);
  color: var(--primary);
}

.approve-batch-btn:hover {
  background: rgba(0, 229, 160, 0.2);
}

.reject-batch-btn {
  background: rgba(255, 107, 107, 0.1);
  color: var(--danger);
}

.reject-batch-btn:hover {
  background: rgba(255, 107, 107, 0.2);
}

.delete-batch-btn {
  background: rgba(255, 71, 87, 0.1);
  color: #ff4757;
}

.delete-batch-btn:hover {
  background: rgba(255, 71, 87, 0.2);
}

.clear-selection-btn {
  background: var(--bg-base);
  color: var(--text-secondary);
  border: 1px solid var(--border-base);
}

.clear-selection-btn:hover {
  background: var(--bg-overlay);
  color: var(--text-primary);
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

.loading-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-10);
  color: var(--text-secondary);
  font-size: var(--text-sm);
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
  background: transparent !important;
}

.modern-table :deep(.el-table__empty-text) {
  color: var(--text-muted);
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.file-icon {
  color: var(--primary);
}

.category-tag {
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-tag {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.status-tag.completed,
.status-tag.review-approved {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-tag.processing {
  background: rgba(245, 158, 11, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.status-tag.failed,
.status-tag.review-rejected {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.status-tag.pending,
.status-tag.review-pending {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-base);
}

.date-text {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.action-buttons {
  display: flex;
  gap: var(--space-2);
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
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.action-btn.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--accent);
  color: var(--accent);
}

.action-btn.approve-btn:hover {
  background: rgba(16, 185, 129, 0.1);
  border-color: var(--success);
  color: var(--success);
}

.action-btn.reject-btn:hover {
  background: rgba(245, 158, 11, 0.1);
  border-color: var(--secondary);
  color: var(--secondary);
}

.reason-text {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.file-size {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.detail-text {
  font-size: var(--text-xs);
  line-height: 1.5;
}

.detail-text.detail-rejected {
  color: var(--secondary);
}

.detail-text.detail-failed {
  color: var(--accent);
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-base);
}

:deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--text-secondary);
  --el-pagination-button-bg-color: var(--bg-elevated);
  --el-pagination-hover-color: var(--primary);
}
</style>
