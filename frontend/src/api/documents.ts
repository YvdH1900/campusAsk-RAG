import api from './request'

export interface DocumentResponse {
  id: number
  filename: string
  file_path: string
  category: string | null
  description: string | null
  file_size: number
  status: string
  review_status: string
  reject_reason: string | null
  uploaded_by: number | null
  reviewed_by: number | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedDocumentsResponse {
  total: number
  page: number
  page_size: number
  pages: number
  items: DocumentResponse[]
}

export function getAllDocuments(page = 1, pageSize = 10, status?: string, reviewStatus?: string) {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (status) params.status = status
  if (reviewStatus) params.review_status = reviewStatus
  return api.get<PaginatedDocumentsResponse>('/api/v1/documents/', { params })
}

export function getPendingDocuments() {
  return api.get<DocumentResponse[]>('/api/v1/documents/pending')
}

export function reviewDocument(documentId: number, data: { action: string; reason?: string }) {
  return api.post<DocumentResponse>(`/api/v1/documents/${documentId}/review`, data)
}

export async function downloadDocument(documentId: number) {
  const token = sessionStorage.getItem('token')
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  
  try {
    // 使用 fetch 下载，支持 Header 认证
    const response = await fetch(`${baseURL}/api/v1/documents/${documentId}/download`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '下载失败' }))
      throw new Error(error.detail || '下载失败')
    }
    
    // 获取文件名（从 Content-Disposition header 解析）
    let filename = 'download'
    const contentDisposition = response.headers.get('content-disposition')
    
    console.log('Content-Disposition header:', contentDisposition)
    
    if (contentDisposition) {
      // 使用更健壮的正则表达式解析文件名
      // 支持格式：attachment; filename*=UTF-8''%E6%96%87%E4%BB%B6%E5%90%8D.txt
      const filenameStarMatch = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;\s]+)/i)
      console.log('RFC 5987 match:', filenameStarMatch)
      
      if (filenameStarMatch && filenameStarMatch[1]) {
        try {
          filename = decodeURIComponent(filenameStarMatch[1])
          console.log('Parsed filename (RFC 5987):', filename)
        } catch (e) {
          filename = filenameStarMatch[1]
          console.log('Parsed filename (raw):', filename)
        }
      } else {
        // 备用：尝试解析普通文件名 (filename="name.txt" 或 filename=name.txt)
        const filenameMatch = contentDisposition.match(/filename\s*=\s*["']?([^;'"\\s]+)["']?/i)
        console.log('Regular match:', filenameMatch)
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1]
          console.log('Parsed filename (regular):', filename)
        }
      }
    }
    
    console.log('Final filename:', filename)
    
    // 清理文件名中的非法字符（跨平台兼容）
    filename = filename.replace(/[<>:"/\\|?*]/g, '_').trim()
    
    // 下载文件
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('下载失败:', error)
    throw error
  }
}

export function previewDocument(documentId: number) {
  return api.get<{ filename: string; content: string; size: number }>(`/api/v1/documents/${documentId}/preview`)
}

export function deleteDocument(documentId: number) {
  return api.delete<{ message: string; filename: string }>(`/api/v1/documents/${documentId}`)
}

export function batchDeleteDocuments(documentIds: number[]) {
  return api.post('/api/v1/documents/batch-delete', { document_ids: documentIds })
}

export function batchReviewDocuments(documentIds: number[], action: string, rejectReason?: string) {
  return api.post('/api/v1/documents/batch-review', {
    document_ids: documentIds,
    action,
    reject_reason: rejectReason,
  })
}
