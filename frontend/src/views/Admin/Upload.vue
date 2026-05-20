<template>
  <div class="admin-upload">
    <div class="page-content">
      <div class="header-content">
        <div class="header-badge">
          <div class="badge-dot"></div>
          <span>DOCUMENT UPLOAD</span>
        </div>
        <h2 class="page-title">文档上传</h2>
        <p class="page-desc">上传文档到知识库，支持多种格式</p>
        <div class="header-line"></div>
      </div>
    </div>

    <div class="upload-container">
      <div class="upload-card">
        <div class="card-glow"></div>
        <div class="card-header">
          <div class="header-left">
            <div class="header-icon-box">
              <el-icon><Upload /></el-icon>
            </div>
            <div class="header-text-group">
              <span class="header-title">上传文档</span>
              <span class="header-subtitle">UPLOAD DOCUMENTS</span>
            </div>
          </div>
        </div>
        <div class="card-divider"></div>

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
              <el-icon :size="48"><UploadFilled /></el-icon>
            </div>
            <p class="upload-text">将文件拖拽到此处，或 <em>点击上传</em></p>
            <p class="upload-hint">支持 PDF、Word、TXT、Markdown 格式</p>
            <p v-if="selectedFile" class="selected-file">
              <el-icon><Document /></el-icon>
              <span>{{ selectedFile.name }}</span>
            </p>
          </div>
        </div>

        <div class="form-section">
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

        <button class="upload-btn" @click="handleUpload" :disabled="uploading || !selectedFile">
          <el-icon v-if="uploading" class="is-loading"><Loading /></el-icon>
          <el-icon v-else><Upload /></el-icon>
          <span>{{ uploading ? '上传中...' : '上传文档' }}</span>
        </button>
      </div>

      <div class="history-card">
        <div class="card-glow"></div>
        <div class="card-header">
          <div class="header-left">
            <div class="header-icon-box">
              <el-icon><Document /></el-icon>
            </div>
            <div class="header-text-group">
              <span class="header-title">已上传文档</span>
              <span class="header-subtitle">UPLOADED DOCUMENTS</span>
            </div>
          </div>
          <button class="refresh-btn" @click="loadDocuments" :disabled="loading">
            <el-icon :size="14"><Refresh /></el-icon>
            <span>{{ loading ? '刷新中...' : '刷新' }}</span>
          </button>
        </div>
        <div class="card-divider"></div>

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
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <span class="status-tag" :class="row.status">
                {{ getStatusText(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="上传时间" width="180">
            <template #default="{ row }">
              <span class="date-text">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Document, UploadFilled, Loading, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const uploading = ref(false)
const documents = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let pollingTimer: number | null = null
let isPollingRequestInProgress = false

const uploadForm = reactive({
  category: '',
  description: '',
})

const formatDate = (date: string) => {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-')
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
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

const startPolling = () => {
  stopPolling()
  pollingTimer = window.setInterval(async () => {
    if (isPollingRequestInProgress) return
    const hasProcessing = documents.value.some((d) => d.status === 'processing')
    if (hasProcessing) {
      isPollingRequestInProgress = true
      try {
        await loadDocuments()
      } finally {
        isPollingRequestInProgress = false
      }
    } else {
      stopPolling()
    }
  }, 5000)
}

const stopPolling = () => {
  if (pollingTimer !== null) {
    clearInterval(pollingTimer)
    pollingTimer = null
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
      },
    })

    ElMessage.success('文档上传成功')
    selectedFile.value = null
    uploadForm.category = ''
    uploadForm.description = ''
    await loadDocuments()
    startPolling()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(() => {
  loadDocuments()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.admin-upload {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.page-content {
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

.upload-container {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: var(--space-6);
  position: relative;
  z-index: 1;
  width: 100%;
}

.upload-card,
.history-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  padding: var(--space-1);
  overflow: hidden;
  position: relative;
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

.card-header {
  padding: var(--space-5) var(--space-5) var(--space-4);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-icon-box {
  width: 40px;
  height: 40px;
  background: var(--primary-subtle);
  border: 1px solid rgba(0, 229, 160, 0.2);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  transition: all var(--duration-normal) var(--ease-out);
}

.header-icon-box:hover {
  background: var(--primary);
  color: white;
  transform: scale(1.05);
  box-shadow: 0 0 20px var(--primary-glow);
}

.header-text-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-0);
}

.header-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.header-subtitle {
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.card-divider {
  height: 1px;
  background: var(--border-base);
  margin: 0 var(--space-5);
}

.upload-area {
  border: 2px dashed var(--border-base);
  border-radius: var(--radius-lg);
  margin: var(--space-5);
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
  width: 72px;
  height: 72px;
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

.form-section {
  padding: var(--space-5);
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

.upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: calc(100% - var(--space-10));
  margin: 0 var(--space-5) var(--space-5);
  background: var(--primary);
  border: none;
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-6);
  color: white;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.upload-btn:hover:not(:disabled) {
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px var(--primary-glow);
}

.upload-btn:active:not(:disabled) {
  transform: translateY(0);
}

.upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-btn {
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

.refresh-btn:hover:not(:disabled) {
  background: var(--bg-subtle);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

.status-tag.processing {
  background: rgba(0, 180, 216, 0.1);
  color: var(--secondary-light);
  border: 1px solid rgba(0, 180, 216, 0.2);
}

.status-tag.completed {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-tag.failed {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.date-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
</style>
