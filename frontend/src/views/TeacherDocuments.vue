<template>
  <div class="teacher-documents">
    <div class="page-content">
      <div class="header-content">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>MY DOCUMENTS</span>
        </div>
        <h2 class="page-title">我的文档</h2>
        <p class="page-desc">管理和上传个人文档资料</p>
        <div class="header-line"></div>
      </div>
      <button class="upload-btn" @click="showUploadDialog = true">
        <el-icon :size="16"><Upload /></el-icon>
        <span>上传文档</span>
      </button>
    </div>

    <div class="content-card">
      <div class="card-glow"></div>
      <el-table :data="documents" style="width: 100%" v-loading="loading" class="modern-table">
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
        <el-table-column prop="review_status" label="审核状态" width="120">
          <template #default="{ row }">
            <span class="status-tag" :class="row.review_status">
              {{ getReviewStatusLabel(row.review_status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="reject_reason" label="驳回理由" width="200">
          <template #default="{ row }">
            <span v-if="row.reject_reason" class="reject-reason">{{ row.reject_reason }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            <span class="date-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
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
              <span v-if="row.review_status === 'rejected'" class="empty-text">文件已删除</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showUploadDialog" title="上传文档" width="520px" class="upload-dialog">
      <div class="dialog-content">
        <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
          <input
            type="file"
            ref="fileInput"
            accept=".pdf,.doc,.docx,.txt,.md"
            class="hidden-input"
            @change="handleFileSelect"
          />
          <div class="upload-content" @click="$refs.fileInput?.click()">
            <div class="upload-icon-wrapper">
              <div class="icon-glow"></div>
              <el-icon :size="40"><UploadFilled /></el-icon>
            </div>
            <p class="upload-text">将文件拖拽到此处，或 <em>点击选择</em></p>
            <p class="upload-hint">支持 PDF、Word、TXT、Markdown 格式</p>
            <p v-if="selectedFile" class="selected-file">
              <el-icon><Document /></el-icon>
              <span>{{ selectedFile.name }}</span>
            </p>
          </div>
        </div>

        <div class="form-fields">
          <div class="form-field">
            <label class="field-label">分类</label>
            <input
              v-model="uploadForm.category"
              type="text"
              class="field-input"
              placeholder="请输入文档分类"
            />
          </div>
          <div class="form-field">
            <label class="field-label">描述</label>
            <textarea
              v-model="uploadForm.description"
              class="field-textarea"
              placeholder="请输入文档描述（可选）"
              rows="3"
            ></textarea>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showUploadDialog = false">取消</button>
          <button class="submit-btn" @click="handleUpload" :disabled="uploading || !selectedFile">
            <el-icon v-if="uploading" class="is-loading"><Loading /></el-icon>
            <span>{{ uploading ? '上传中...' : '上传' }}</span>
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Document, UploadFilled, Loading, View, Download } from '@element-plus/icons-vue'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { downloadDocument, previewDocument } from '@/api/documents'

const userStore = useUserStore()
const loading = ref(false)
const uploading = ref(false)
const showUploadDialog = ref(false)
const documents = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const uploadForm = reactive({
  category: '',
  description: '',
})

const getReviewStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
  }
  return map[status] || 'info'
}

const getReviewStatusLabel = (status: string) => {
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

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    selectedFile.value = event.dataTransfer.files[0]
  }
}

const loadDocuments = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const response = await axios.get('/api/v1/documents/my', {
      headers: { Authorization: `Bearer ${userStore.token}` },
    })
    documents.value = response.data
  } catch (error: any) {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    if (uploadForm.category) formData.append('category', uploadForm.category)
    if (uploadForm.description) formData.append('description', uploadForm.description)

    await axios.post('/api/v1/documents/upload', formData, {
      headers: {
        Authorization: `Bearer ${userStore.token}`,
        'Content-Type': 'multipart/form-data',
      },
    })

    ElMessage.success('文档上传成功，请等待管理员审核')
    showUploadDialog.value = false
    selectedFile.value = null
    uploadForm.category = ''
    uploadForm.description = ''
    await loadDocuments()
  } catch (error: any) {
    const msg = error.response?.data?.detail || '上传失败，请重试'
    ElMessage.error(msg)
  } finally {
    uploading.value = false
  }
}

const handleDownload = (doc: any) => {
  downloadDocument(doc.id)
  ElMessage.success('开始下载文档')
}

const handlePreview = async (doc: any) => {
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
.teacher-documents {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding-top: var(--space-6);
}

.page-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-7);
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

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--primary);
  border: none;
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-5);
  color: white;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  flex-shrink: 0;
}

.upload-btn:hover {
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px var(--primary-glow);
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

.file-name-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.file-icon {
  color: var(--primary-light);
  flex-shrink: 0;
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
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.status-tag.pending {
  background: rgba(245, 158, 11, 0.1);
  color: var(--secondary);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.status-tag.approved {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-tag.rejected {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.reject-reason {
  color: var(--accent-light);
  font-size: var(--text-xs);
}

.empty-text {
  color: var(--text-muted);
}

.date-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.upload-dialog :deep(.el-dialog) {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  overflow: hidden;
}

.upload-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-base);
  padding: var(--space-5) var(--space-6);
  margin: 0;
}

.upload-dialog :deep(.el-dialog__title) {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.upload-dialog :deep(.el-dialog__body) {
  padding: var(--space-6);
}

.upload-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid var(--border-base);
  padding: var(--space-4) var(--space-6);
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.upload-area {
  border: 2px dashed var(--border-base);
  border-radius: var(--radius-lg);
  transition: all var(--duration-normal) var(--ease-out);
  cursor: pointer;
}

.upload-area:hover {
  border-color: var(--primary);
  background: var(--primary-subtle);
}

.hidden-input {
  display: none;
}

.upload-content {
  text-align: center;
  padding: var(--space-8) var(--space-5);
}

.upload-icon-wrapper {
  width: 56px;
  height: 56px;
  background: var(--primary-subtle);
  border: 1px solid var(--border-focus);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  margin: 0 auto var(--space-4);
  position: relative;
  transition: all var(--duration-normal) var(--ease-out);
}

.icon-glow {
  position: absolute;
  inset: -4px;
  background: var(--primary);
  border-radius: inherit;
  opacity: 0;
  filter: blur(8px);
  transition: opacity var(--duration-normal) var(--ease-out);
}

.upload-area:hover .upload-icon-wrapper {
  transform: scale(1.05);
}

.upload-area:hover .icon-glow {
  opacity: 0.3;
}

.upload-text {
  margin: var(--space-3) 0 var(--space-1);
  color: var(--text-secondary);
  font-size: var(--text-base);
}

.upload-text em {
  color: var(--primary);
  font-style: normal;
  font-weight: var(--font-medium);
}

.upload-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.selected-file {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  color: var(--primary-light);
  font-size: var(--text-sm);
}

.form-fields {
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
.field-textarea {
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
.field-textarea:focus {
  border-color: var(--primary);
  background: var(--bg-overlay);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.field-input::placeholder,
.field-textarea::placeholder {
  color: var(--text-muted);
}

.field-textarea {
  resize: vertical;
  min-height: 80px;
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
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.action-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.action-btn.preview-btn:hover {
  background: rgba(0, 229, 160, 0.1);
  border-color: var(--primary);
  color: var(--primary);
}

.action-btn.download-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--info);
  color: var(--info);
}

:deep(.preview-dialog) {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
}

:deep(.preview-dialog .el-message-box__content) {
  max-height: 60vh;
  overflow-y: auto;
}
</style>
