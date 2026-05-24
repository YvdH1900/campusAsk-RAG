<template>
  <div class="site-management">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">网站管理</h1>
        <p class="page-description">管理网站公告、系统设置和模型配置</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="site-tabs" @tab-change="handleTabChange" v-loading="loading && !dataLoaded">
      <!-- 公告管理 -->
      <el-tab-pane label="公告管理" name="announcements">
        <div class="tab-content" v-if="loadedTabs.has('announcements')">
          <div class="content-header">
            <h2>公告列表</h2>
            <el-button type="primary" @click="showAddAnnouncement = true">
              <el-icon><Plus /></el-icon>
              新增公告
            </el-button>
          </div>
          
          <el-table :data="announcements" border v-loading="loading">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="is_active" label="状态" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.is_active ? 'success' : 'warning'">
                  {{ scope.row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_popup" label="弹窗" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.is_popup ? 'primary' : 'info'">
                  {{ scope.row.is_popup ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                <span>{{ formatDateTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="scope">
                <div style="display: flex; gap: 8px;">
                  <el-button 
                    size="small" 
                    @click="editAnnouncement(scope.row)"
                    type="primary"
                    plain
                  >
                    编辑
                  </el-button>
                  <el-button 
                    size="small" 
                    type="danger"
                    plain
                    @click="deleteAnnouncement(scope.row.id)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 系统设置 -->
      <el-tab-pane label="系统设置" name="settings">
        <div class="tab-content" v-if="loadedTabs.has('settings')">
          <div class="settings-card">
            <h3 class="settings-title">网站注册</h3>
            <p class="settings-desc">控制网站是否允许新用户注册</p>
            <div class="setting-control">
              <span class="control-label">注册状态</span>
              <el-switch 
                :model-value="registrationEnabled" 
                @change="updateSetting('registration-enabled', $event)"
                active-text="开启"
                inactive-text="关闭"
              />
            </div>
          </div>

          <div class="settings-card">
            <h3 class="settings-title">网站登录</h3>
            <p class="settings-desc">控制网站登录功能（管理员除外）</p>
            <div class="setting-control">
              <span class="control-label">登录状态</span>
              <el-switch 
                :model-value="loginEnabled" 
                @change="updateSetting('login-enabled', $event)"
                active-text="开启"
                inactive-text="关闭"
              />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 模型管理 -->
      <el-tab-pane label="模型管理" name="models">
        <div class="tab-content" v-if="loadedTabs.has('models')">
          <div class="content-header">
            <h2>模型配置</h2>
          </div>

          <!-- 语言模型配置 -->
          <div class="settings-card">
            <h3 class="settings-title">
              <el-icon class="mr-2"><ChatDotRound /></el-icon>
              语言模型 (LLM)
              <span v-if="currentLlmModelName" class="current-model-badge">
                <el-icon><Check /></el-icon>
                当前使用：{{ currentLlmModelName }}
              </span>
            </h3>
            <p class="settings-desc">配置用于对话生成的语言模型</p>
            <div class="model-config-form">
              <div class="form-row">
                <label class="form-label">模型名称</label>
                <el-input 
                  v-model="llmConfig.model_name" 
                  placeholder="当前仅支持通义千问，如：qwen-plus"
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API Key</label>
                <el-input 
                  v-model="llmConfig.api_key" 
                  placeholder="请输入 API 密钥"
                  type="password"
                  show-password
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API 基础 URL</label>
                <el-input 
                  v-model="llmConfig.api_base_url" 
                  placeholder="可选，默认使用官方地址"
                  class="form-input"
                />
              </div>
              <div class="form-actions">
                <el-button type="info" plain @click="testLlmModel">
                  <el-icon class="mr-1"><Connection /></el-icon>
                  测试连通性
                </el-button>
                <el-button type="primary" @click="saveLlmConfig">
                  <el-icon class="mr-1"><Check /></el-icon>
                  保存并激活
                </el-button>
              </div>
            </div>
          </div>

          <!-- 向量模型配置 -->
          <div class="settings-card">
            <h3 class="settings-title">
              <el-icon class="mr-2"><Grid /></el-icon>
              向量模型 (Embedding)
              <span v-if="currentEmbeddingModelName" class="current-model-badge">
                <el-icon><Check /></el-icon>
                当前使用：{{ currentEmbeddingModelName }}
              </span>
            </h3>
            <p class="settings-desc">配置用于文档向量化的嵌入模型</p>
            <div class="model-config-form">
              <div class="form-row">
                <label class="form-label">模型名称</label>
                <el-input 
                  v-model="embeddingConfig.model_name" 
                  placeholder="如：text-embedding-v3"
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API Key</label>
                <el-input 
                  v-model="embeddingConfig.api_key" 
                  placeholder="请输入 API 密钥"
                  type="password"
                  show-password
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API 基础 URL</label>
                <el-input 
                  v-model="embeddingConfig.api_base_url" 
                  placeholder="可选，默认使用官方地址"
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">向量维度</label>
                <el-input-number 
                  v-model="embeddingConfig.dimension" 
                  :min="128" 
                  :max="4096" 
                  :step="128"
                  placeholder="如：1024 或 1536"
                  class="form-input"
                />
                <span class="form-hint">常见维度：1024 (text-embedding-v2), 1536 (text-embedding-v3)</span>
              </div>
              <div class="form-actions">
                <el-button type="info" plain @click="testEmbeddingModel">
                  <el-icon class="mr-1"><Connection /></el-icon>
                  测试连通性
                </el-button>
                <el-button type="primary" @click="saveEmbeddingConfig">
                  <el-icon class="mr-1"><Check /></el-icon>
                  保存并激活
                </el-button>
              </div>
            </div>
          </div>

          <!-- 重排序模型配置 -->
          <div class="settings-card">
            <h3 class="settings-title">
              <el-icon class="mr-2"><Sort /></el-icon>
              重排序模型 (Reranker)
              <span v-if="currentRerankerModelName" class="current-model-badge">
                <el-icon><Check /></el-icon>
                当前使用：{{ currentRerankerModelName }}
              </span>
              <el-tag v-else type="info" size="small" class="ml-2">使用启发式重排序</el-tag>
            </h3>
            <p class="settings-desc">
              配置阿里云百炼平台的 Reranker API，提升检索结果排序质量。
              推荐模型：gte-rerank。未配置时将使用基于分数的启发式重排序（零成本）。
            </p>
            <div class="model-config-form">
              <div class="form-row">
                <label class="form-label">模型名称</label>
                <el-input 
                  v-model="rerankerConfig.model_name" 
                  placeholder="如：gte-rerank"
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API Key</label>
                <el-input 
                  v-model="rerankerConfig.api_key" 
                  placeholder="请输入阿里云百炼平台 API Key"
                  type="password"
                  show-password
                  class="form-input"
                />
              </div>
              <div class="form-row">
                <label class="form-label">API 基础 URL</label>
                <el-input 
                  v-model="rerankerConfig.api_base_url" 
                  placeholder="可选，默认使用阿里云官方地址"
                  class="form-input"
                />
              </div>
              <div class="form-actions">
                <el-button type="info" plain @click="testRerankerModel">
                  <el-icon class="mr-1"><Connection /></el-icon>
                  测试连通性
                </el-button>
                <el-button type="primary" @click="saveRerankerConfig">
                  <el-icon class="mr-1"><Check /></el-icon>
                  保存并激活
                </el-button>
              </div>
            </div>
          </div>

          <!-- 功能模型信息 -->
          <div class="settings-card model-info-card">
            <h3 class="settings-title">
              <el-icon class="mr-2"><InfoFilled /></el-icon>
              功能模型使用情况
            </h3>
            <p class="settings-desc">以下功能使用通义千问 LLM，无需额外配置</p>
            <div class="model-info-grid">
              <div class="model-info-item">
                <div class="model-info-icon">
                  <el-icon><Search /></el-icon>
                </div>
                <div class="model-info-content">
                  <div class="model-info-name">查询扩展</div>
                  <div class="model-info-desc">使用 LLM 生成语义相似的变体问题</div>
                  <el-tag type="success" size="small">通义千问 LLM</el-tag>
                </div>
              </div>
              <div class="model-info-item">
                <div class="model-info-icon">
                  <el-icon><ChatLineSquare /></el-icon>
                </div>
                <div class="model-info-content">
                  <div class="model-info-name">对话摘要</div>
                  <div class="model-info-desc">使用 LLM 压缩过长对话历史</div>
                  <el-tag type="success" size="small">通义千问 LLM</el-tag>
                </div>
              </div>
              <div class="model-info-item">
                <div class="model-info-icon">
                  <el-icon><CircleCheck /></el-icon>
                </div>
                <div class="model-info-content">
                  <div class="model-info-name">答案验证</div>
                  <div class="model-info-desc">使用 LLM 验证答案是否基于上下文</div>
                  <el-tag type="success" size="small">通义千问 LLM</el-tag>
                </div>
              </div>
              <div class="model-info-item">
                <div class="model-info-icon">
                  <el-icon><Sort /></el-icon>
                </div>
                <div class="model-info-content">
                  <div class="model-info-name">重排序</div>
                  <div class="model-info-desc">使用阿里云 Reranker API 或启发式算法</div>
                  <el-tag :type="currentRerankerModelName ? 'success' : 'info'" size="small">
                    {{ currentRerankerModelName ? 'API 重排序' : '启发式重排序' }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 登录记录 -->
      <el-tab-pane label="登录记录" name="loginRecords">
        <div class="tab-content" v-if="loadedTabs.has('loginRecords')">
          <div class="content-header">
            <h2>登录记录</h2>
            <el-button type="danger" @click="cleanupLoginRecords">
              <el-icon><Delete /></el-icon>
              清理过期记录
            </el-button>
          </div>

          <el-table :data="loginRecords" border>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="login_time" label="登录时间" width="180">
              <template #default="{ row }">
                <span>{{ formatDateTime(row.login_time) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="ip_address" label="IP 地址" />
            <el-table-column prop="success" label="状态" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.success ? 'success' : 'danger'">
                  {{ scope.row.success ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="failure_reason" label="失败原因" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 公告弹窗 -->
    <el-dialog title="公告管理" v-model="showAddAnnouncement" width="600px">
      <el-form :model="announcementForm" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="announcementForm.title" placeholder="请输入公告标题" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="announcementForm.content" type="textarea" :rows="4" placeholder="请输入公告内容" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="announcementForm.is_active" />
        </el-form-item>
        <el-form-item label="弹窗显示">
          <el-switch v-model="announcementForm.is_popup" />
        </el-form-item>
        <el-form-item label="只显示一次">
          <el-switch v-model="announcementForm.show_once" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddAnnouncement = false">取消</el-button>
        <el-button type="primary" @click="saveAnnouncement">保存</el-button>
      </template>
    </el-dialog>

    <!-- 向量模型重建进度对话框 -->
    <el-dialog 
      v-model="showRebuildProgress" 
      title="向量模型重建进度" 
      width="600px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="rebuild-progress-dialog">
        <div class="progress-info">
          <el-icon class="rotating-icon" v-if="progressStatus === 'processing'"><Loading /></el-icon>
          <el-icon class="success-icon" v-else-if="progressStatus === 'completed'"><CircleCheck /></el-icon>
          <el-icon class="error-icon" v-else-if="progressStatus === 'failed'"><CircleClose /></el-icon>
          <span class="progress-stage">{{ progressStage }}</span>
        </div>
        
        <el-progress 
          :percentage="progressPercent" 
          :status="progressStatus === 'failed' ? 'exception' : (progressStatus === 'completed' ? 'success' : undefined)"
          :stroke-width="20"
        />
        
        <div class="progress-message">
          {{ progressMessage }}
        </div>
        
        <div class="progress-details" v-if="progressDetails">
          <el-divider />
          <p>{{ progressDetails }}</p>
        </div>
      </div>
      
      <template #footer>
        <el-button 
          v-if="progressStatus === 'completed' || progressStatus === 'failed'" 
          type="primary" 
          @click="closeProgressDialog"
        >
          {{ progressStatus === 'failed' ? '关闭' : '完成' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Check, ChatDotRound, Grid, Connection, Loading, CircleCheck, CircleClose, Sort, InfoFilled, Search, ChatLineSquare } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('announcements')
const showAddAnnouncement = ref(false)
const loading = ref(false)
const dataLoaded = ref(false)

const announcements = ref<any[]>([])
const announcementForm = reactive({
  id: null,
  title: '',
  content: '',
  is_active: true,
  is_popup: true,
  show_once: true
})

const registrationEnabled = ref(true)
const loginEnabled = ref(true)

const llmConfig = reactive({
  id: null as number | null,
  model_name: '',
  api_key: '',
  api_base_url: ''
})

const embeddingConfig = reactive({
  id: null as number | null,
  model_name: '',
  api_key: '',
  api_base_url: '',
  dimension: 1024 as number | null
})

const rerankerConfig = reactive({
  id: null as number | null,
  model_name: '',
  api_key: '',
  api_base_url: ''
})

// 当前实际使用的模型（从服务器读取）
const currentLlmModelName = ref<string>('')
const currentEmbeddingModelName = ref<string>('')
const currentRerankerModelName = ref<string>('')

const loginRecords = ref<any[]>([])

const loadedTabs = new Set<string>(['announcements'])

const handleTabChange = (tab: string) => {
  if (loadedTabs.has(tab)) return
  
  loadedTabs.add(tab)
  
  if (tab === 'settings') {
    fetchSettings()
  } else if (tab === 'models') {
    fetchModelConfigs()
  } else if (tab === 'loginRecords') {
    fetchLoginRecords()
  }
}

// 进度条相关状态
const showRebuildProgress = ref(false)
const progressTaskId = ref<string | null>(null)
const progressPercent = ref(0)
const progressStage = ref('')
const progressMessage = ref('')
const progressDetails = ref('')
const progressStatus = ref<'pending' | 'processing' | 'completed' | 'failed'>('pending')
let progressPollingInterval: number | null = null

/**
 * 格式化时间为北京时间格式
 */
const formatDateTime = (dateStr: string) => {
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

const fetchAnnouncements = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/v1/admin/announcements', {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const result = await response.json()
      announcements.value = Array.isArray(result) ? result : (result.items || [])
    } else {
      console.error('获取公告失败，状态码:', response.status)
      ElMessage.error('获取公告列表失败')
    }
  } catch (error) {
    console.error('获取公告失败:', error)
    ElMessage.error('获取公告列表失败：' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    loading.value = false
  }
}

const saveAnnouncement = async () => {
  try {
    const method = announcementForm.id ? 'PUT' : 'POST'
    const url = announcementForm.id 
      ? `/api/v1/admin/announcements/${announcementForm.id}` 
      : '/api/v1/admin/announcements'
    
    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(announcementForm)
    })
    
    if (response.ok) {
      showAddAnnouncement.value = false
      announcementForm.id = null
      announcementForm.title = ''
      announcementForm.content = ''
      announcementForm.is_active = true
      announcementForm.is_popup = true
      announcementForm.show_once = true
      await fetchAnnouncements()
    }
  } catch (error) {
    console.error('保存公告失败:', error)
  }
}

const editAnnouncement = (row: any) => {
  announcementForm.id = row.id
  announcementForm.title = row.title
  announcementForm.content = row.content
  announcementForm.is_active = row.is_active
  announcementForm.is_popup = row.is_popup
  announcementForm.show_once = row.show_once
  showAddAnnouncement.value = true
}

const deleteAnnouncement = async (id: number) => {
  try {
    const response = await fetch(`/api/v1/admin/announcements/${id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      await fetchAnnouncements()
    }
  } catch (error) {
    console.error('删除公告失败:', error)
  }
}

const fetchSettings = async () => {
  try {
    const response = await fetch('/api/v1/admin/settings', {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const settings = await response.json()
      const settingsMap: Record<string, string> = {}
      if (Array.isArray(settings)) {
        settings.forEach(setting => {
          settingsMap[setting.setting_key] = setting.setting_value
        })
      }
      registrationEnabled.value = settingsMap['registration_enabled'] === 'true'
      loginEnabled.value = settingsMap['login_enabled'] === 'true'
    }
  } catch (error) {
    console.error('获取设置失败:', error)
  }
}

const updateSetting = async (key: string, value: boolean) => {
  try {
    const response = await fetch(`/api/v1/admin/settings/${key}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ setting_value: value ? 'true' : 'false' })
    })
    if (response.ok) {
      if (key === 'registration-enabled') {
        registrationEnabled.value = value
      } else if (key === 'login-enabled') {
        loginEnabled.value = value
      }
    }
  } catch (error) {
    console.error('更新设置失败:', error)
  }
}

const fetchModelConfigs = async () => {
  try {
    const response = await fetch('/api/v1/admin/model-configs', {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const result = await response.json()
      const configs = Array.isArray(result) ? result : (result.items || [])
      
      const llm = configs.find((c: any) => c.model_type === 'llm' && c.is_active)
      if (llm) {
        llmConfig.id = llm.id
        llmConfig.model_name = llm.model_name
        llmConfig.api_key = llm.api_key
        llmConfig.api_base_url = llm.api_base_url || ''
        currentLlmModelName.value = llm.model_name
      }
      
      const embedding = configs.find((c: any) => c.model_type === 'embedding' && c.is_active)
      if (embedding) {
        embeddingConfig.id = embedding.id
        embeddingConfig.model_name = embedding.model_name
        embeddingConfig.api_key = embedding.api_key
        embeddingConfig.api_base_url = embedding.api_base_url || ''
        embeddingConfig.dimension = embedding.dimension || 1024
        currentEmbeddingModelName.value = embedding.model_name
      }

      const reranker = configs.find((c: any) => c.model_type === 'reranker' && c.is_active)
      if (reranker) {
        rerankerConfig.id = reranker.id
        rerankerConfig.model_name = reranker.model_name
        rerankerConfig.api_key = reranker.api_key
        rerankerConfig.api_base_url = reranker.api_base_url || ''
        currentRerankerModelName.value = reranker.model_name
      }
    }
    
    if (!currentLlmModelName.value || !currentEmbeddingModelName.value) {
      const modelInfoResponse = await fetch('/api/v1/chat/model-info')
      if (modelInfoResponse.ok) {
        const modelInfo = await modelInfoResponse.json()
        if (!currentLlmModelName.value && modelInfo.llm_model_name) {
          currentLlmModelName.value = modelInfo.llm_model_name
        }
        if (!currentEmbeddingModelName.value && modelInfo.embedding_model_name) {
          currentEmbeddingModelName.value = modelInfo.embedding_model_name
        }
      }
    }
  } catch (error) {
    console.error('获取模型配置失败:', error)
  }
}

const testLlmModel = async () => {
  if (!llmConfig.model_name || !llmConfig.api_key) {
    ElMessage.warning('请填写模型名称和 API Key')
    return
  }
  try {
    const response = await fetch('/api/v1/admin/model-configs/test', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'llm',
        model_name: llmConfig.model_name,
        api_key: llmConfig.api_key,
        api_base_url: llmConfig.api_base_url || undefined
      })
    })
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        const dimInfo = result.actual_dimension ? `（维度: ${result.actual_dimension}）` : ''
        ElMessage.success('测试成功！Embedding 模型连通正常' + dimInfo)
      } else {
        ElMessage.error('测试失败：' + (result.message || '未知错误'))
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('测试失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('测试模型失败:', error)
    ElMessage.error('测试失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const saveLlmConfig = async () => {
  if (!llmConfig.model_name || !llmConfig.api_key) {
    ElMessage.warning('请填写模型名称和 API Key')
    return
  }
  try {
    let url = '/api/v1/admin/model-configs'
    let method = 'POST'
    
    if (llmConfig.id) {
      url = `/api/v1/admin/model-configs/${llmConfig.id}`
      method = 'PUT'
    }
    
    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'llm',
        model_name: llmConfig.model_name,
        api_key: llmConfig.api_key,
        api_base_url: llmConfig.api_base_url || undefined
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      llmConfig.id = data.id
      
      await activateModelById(data.id)
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('保存失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('保存模型配置失败:', error)
    ElMessage.error('保存失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const testEmbeddingModel = async () => {
  if (!embeddingConfig.model_name || !embeddingConfig.api_key) {
    ElMessage.warning('请填写模型名称和 API Key')
    return
  }
  try {
    const response = await fetch('/api/v1/admin/model-configs/test', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'embedding',
        model_name: embeddingConfig.model_name,
        api_key: embeddingConfig.api_key,
        api_base_url: embeddingConfig.api_base_url || undefined,
        dimension: embeddingConfig.dimension || 1024
      })
    })
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        ElMessage.success('测试成功！')
      } else {
        ElMessage.error('测试失败：' + (result.message || '未知错误'))
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('测试失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('测试模型失败:', error)
    ElMessage.error('测试失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const saveEmbeddingConfig = async () => {
  if (!embeddingConfig.model_name || !embeddingConfig.api_key) {
    ElMessage.warning('请填写模型名称和 API Key')
    return
  }
  
  try {
    let url = '/api/v1/admin/model-configs'
    let method = 'POST'
    
    if (embeddingConfig.id) {
      url = `/api/v1/admin/model-configs/${embeddingConfig.id}`
      method = 'PUT'
    }
    
    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'embedding',
        model_name: embeddingConfig.model_name,
        api_key: embeddingConfig.api_key,
        api_base_url: embeddingConfig.api_base_url || undefined,
        dimension: embeddingConfig.dimension || undefined
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      embeddingConfig.id = data.id
      
      try {
        await ElMessageBox.confirm(
          `切换向量模型将重建整个向量库，此过程可能需要较长时间（取决于文档数量）。<br/><br/>
           重建期间：<br/>
           • 文档搜索功能将暂时不可用<br/>
           • 请勿关闭页面或刷新<br/>
           • 进度条将显示实时进度<br/><br/>
           确定要继续吗？`,
          '确认切换向量模型',
          {
            dangerouslyUseHTMLString: true,
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
      } catch (cancelError) {
        return
      }
      
      const activateResponse = await fetch(`/api/v1/admin/model-configs/${data.id}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      })
      
      if (activateResponse.ok) {
        const activateData = await activateResponse.json()
        
        if (activateData.task_id) {
          startProgressPolling(activateData.task_id)
        } else {
          ElMessage.success(activateData.message || '模型切换成功！')
          await fetchModelConfigs()
        }
      } else {
        const errorData = await activateResponse.json().catch(() => ({}))
        ElMessage.error('激活失败：' + (errorData.detail || `HTTP ${activateResponse.status}`))
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('保存失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('保存模型配置失败:', error)
    ElMessage.error('保存失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const activateModelById = async (id: number) => {
  try {
    const response = await fetch(`/api/v1/admin/model-configs/${id}/activate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const data = await response.json()
      ElMessage.success(data.message || '模型激活成功！')
      await fetchModelConfigs()
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('激活失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('激活模型失败:', error)
    ElMessage.error('激活失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const testRerankerModel = async () => {
  if (!rerankerConfig.model_name) {
    ElMessage.warning('请填写模型名称')
    return
  }
  try {
    const response = await fetch('/api/v1/admin/model-configs/test', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'reranker',
        model_name: rerankerConfig.model_name,
        api_key: rerankerConfig.api_key || '',
        api_base_url: rerankerConfig.api_base_url || undefined
      })
    })
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        ElMessage.success(`测试通过！${data.message}，耗时 ${data.latency_ms}ms`)
      } else {
        ElMessage.error(data.message || '测试失败')
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('测试失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('测试模型失败:', error)
    ElMessage.error('测试失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

const saveRerankerConfig = async () => {
  if (!rerankerConfig.model_name) {
    ElMessage.warning('请填写模型名称')
    return
  }
  
  try {
    let url = '/api/v1/admin/model-configs'
    let method = 'POST'
    
    if (rerankerConfig.id) {
      url = `/api/v1/admin/model-configs/${rerankerConfig.id}`
      method = 'PUT'
    }
    
    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_type: 'reranker',
        model_name: rerankerConfig.model_name,
        api_key: rerankerConfig.api_key || '',
        api_base_url: rerankerConfig.api_base_url || undefined
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      rerankerConfig.id = data.id
      
      const activateResponse = await fetch(`/api/v1/admin/model-configs/${data.id}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      })
      
      if (activateResponse.ok) {
        const activateData = await activateResponse.json()
        ElMessage.success(activateData.message || '重排序模型切换成功！')
        await fetchModelConfigs()
      } else {
        const errorData = await activateResponse.json().catch(() => ({}))
        ElMessage.error('激活失败：' + (errorData.detail || `HTTP ${activateResponse.status}`))
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      ElMessage.error('保存失败：' + (errorData.detail || `HTTP ${response.status}`))
    }
  } catch (error) {
    console.error('保存模型配置失败:', error)
    ElMessage.error('保存失败：' + (error instanceof Error ? error.message : '未知错误'))
  }
}

// 进度条相关方法
const startProgressPolling = (taskId: string) => {
  progressTaskId.value = taskId
  progressStatus.value = 'processing'
  progressPercent.value = 0
  progressStage.value = '初始化'
  progressMessage.value = '正在准备重建环境'
  progressDetails.value = ''
  showRebuildProgress.value = true
  
  pollProgress(taskId)
  progressPollingInterval = window.setInterval(() => {
    pollProgress(taskId)
  }, 2000)
}

const pollProgress = async (taskId: string) => {
  try {
    const response = await fetch(`/api/v1/admin/model-configs/rebuild-progress/${taskId}`, {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      progressPercent.value = data.progress || 0
      progressStage.value = data.stage || ''
      progressMessage.value = data.message || ''
      progressStatus.value = data.status as 'pending' | 'processing' | 'completed' | 'failed'
      
      if (data.status === 'completed' || data.status === 'failed') {
        if (progressPollingInterval) {
          clearInterval(progressPollingInterval)
          progressPollingInterval = null
        }
        
        if (data.status === 'completed') {
          // 更新当前使用的模型名称
          currentEmbeddingModelName.value = embeddingConfig.model_name
          await fetchModelConfigs()
        } else if (data.status === 'failed') {
          // 失败时，恢复显示原来的模型名称
          ElMessage.error(data.error_message || '向量库重建失败，已恢复到原模型')
          await fetchModelConfigs()
        }
      }
    }
  } catch (error) {
    console.error('获取进度失败:', error)
  }
}

const closeProgressDialog = () => {
  showRebuildProgress.value = false
  progressTaskId.value = null
  progressPercent.value = 0
  progressStage.value = ''
  progressMessage.value = ''
  progressDetails.value = ''
  progressStatus.value = 'pending'
  
  if (progressPollingInterval) {
    clearInterval(progressPollingInterval)
    progressPollingInterval = null
  }
}

const fetchLoginRecords = async () => {
  try {
    const response = await fetch('/api/v1/admin/login-records?page=1&page_size=100', {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const result = await response.json()
      loginRecords.value = result.items || []
    }
  } catch (error) {
    console.error('获取登录记录失败:', error)
  }
}

const cleanupLoginRecords = async () => {
  try {
    await ElMessageBox.confirm(
      '将清理 30 天前的登录记录，确定要继续吗？',
      '清理过期记录',
      {
        confirmButtonText: '确定清理',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const response = await fetch('/api/v1/admin/login-records/cleanup', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      const data = await response.json()
      ElMessage.success(data.message || '清理成功')
      await fetchLoginRecords()
    } else {
      const errorData = await response.json()
      ElMessage.error('清理失败：' + (errorData.detail || '未知错误'))
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清理登录记录失败:', error)
      ElMessage.error('清理登录记录失败')
    }
  }
}

const loadAllData = async () => {
  loading.value = true
  try {
    await fetchAnnouncements()
    dataLoaded.value = true
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAllData()
})
</script>

<style scoped lang="scss">
.site-management {
  padding: var(--space-6);
  min-height: 100%;
}

.page-header {
  margin-bottom: var(--space-6);
  
  .header-content {
    max-width: 1200px;
    margin: 0 auto;
  }
  
  .page-title {
    font-size: var(--text-3xl);
    font-weight: var(--font-bold);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .page-description {
    font-size: var(--text-base);
    color: var(--text-secondary);
    margin: 0;
  }
}

.site-tabs {
  max-width: 1200px;
  margin: 0 auto;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  border: 1px solid var(--border-base);
}

:deep(.el-tabs__header) {
  margin-bottom: var(--space-5);
  border-bottom: 1px solid var(--border-base);
}

:deep(.el-tabs__item) {
  font-size: var(--text-base);
  padding: var(--space-3) var(--space-5);
  color: var(--text-secondary);
  transition: all 0.3s ease;
  
  &:hover {
    color: var(--primary);
  }
  
  &.is-active {
    color: var(--primary);
    font-weight: var(--font-semibold);
  }
}

:deep(.el-tabs__active-bar) {
  background: var(--primary-gradient) !important;
  height: 2px !important;
  border-radius: 1px;
}

.tab-content {
  padding: var(--space-5);
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
  gap: var(--space-3);
}

.content-header h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  flex-shrink: 0;
}

.settings-card {
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
  border: 1px solid var(--border-base);
}

.settings-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--space-1);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.current-model-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  background: rgba(0, 229, 160, 0.1);
  border: 1px solid rgba(0, 229, 160, 0.3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--primary);
  font-weight: var(--font-medium);
  margin-left: var(--space-2);
}

.settings-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--space-4);
}

.setting-control {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.control-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  min-width: 80px;
}

.model-config-form {
  margin-top: var(--space-4);
}

.form-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.form-label {
  min-width: 100px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
  flex-shrink: 0;
}

.form-input {
  flex: 1;
  max-width: 480px;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: var(--space-2);
  white-space: nowrap;
}

.form-actions {
  display: flex;
  gap: var(--space-3);
  padding-left: calc(100px + var(--space-4));
}

.form-actions :deep(.el-button--info) {
  background: var(--bg-subtle) !important;
  border: 1px solid var(--border-base) !important;
  color: var(--text-primary) !important;
}

.form-actions :deep(.el-button--info:hover) {
  background: rgba(255, 255, 255, 0.08) !important;
  border-color: var(--border-hover) !important;
  color: var(--text-primary) !important;
}

.form-actions :deep(.el-button--primary) {
  background: var(--primary-gradient) !important;
  border: none !important;
  color: #fff !important;
  font-weight: var(--font-semibold) !important;
}

.form-actions :deep(.el-button--primary:hover) {
  opacity: 0.9;
  transform: translateY(-1px);
}

:deep(.el-button--primary.is-plain) {
  color: var(--primary) !important;
  background: rgba(0, 229, 160, 0.1) !important;
  border: 1px solid var(--primary) !important;
  font-weight: var(--font-semibold) !important;
}

:deep(.el-button--primary.is-plain:hover) {
  color: #fff !important;
  background: var(--primary) !important;
  border-color: var(--primary) !important;
}

:deep(.el-button--danger.is-plain) {
  color: var(--error) !important;
  background: rgba(244, 67, 54, 0.1) !important;
  border: 1px solid var(--error) !important;
  font-weight: var(--font-semibold) !important;
}

:deep(.el-button--danger.is-plain:hover) {
  color: #fff !important;
  background: var(--error) !important;
  border-color: var(--error) !important;
}

/* 表格中的按钮布局 */
:deep(.el-table .cell .el-button) {
  margin: 0 4px;
}

:deep(.el-progress__text) {
  font-size: var(--text-sm) !important;
  color: var(--text-secondary) !important;
}

/* 功能模型信息卡片 */
.model-info-card {
  background: linear-gradient(135deg, rgba(0, 229, 160, 0.05), rgba(0, 176, 255, 0.05));
  border-color: rgba(0, 229, 160, 0.15);
}

.model-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.model-info-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-base);
  transition: all 0.2s ease;
}

.model-info-item:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
}

.model-info-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 229, 160, 0.1);
  border-radius: var(--radius-md);
  color: var(--primary);
  font-size: 20px;
  flex-shrink: 0;
}

.model-info-content {
  flex: 1;
  min-width: 0;
}

.model-info-name {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.model-info-desc {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
  line-height: 1.5;
}

.rebuild-progress-dialog {
  padding: var(--space-4);
  
  .progress-info {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    
    .rotating-icon {
      color: var(--primary);
      font-size: 20px;
      animation: rotating 1.5s linear infinite;
    }
    
    .success-icon {
      color: var(--success);
      font-size: 20px;
    }
    
    .error-icon {
      color: var(--danger);
      font-size: 20px;
    }
    
    .progress-stage {
      font-size: var(--text-base);
      font-weight: var(--font-medium);
      color: var(--text-primary);
    }
  }
  
  .progress-message {
    margin-top: var(--space-3);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.6;
  }
  
  .progress-details {
    margin-top: var(--space-3);
    
    p {
      margin: 0;
      font-size: var(--text-xs);
      color: var(--text-secondary);
      line-height: 1.6;
    }
  }
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
