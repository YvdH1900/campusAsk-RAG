import api from './request'

export interface ChatAskRequest {
  content: string
  session_id?: number | null
  stream?: boolean
  top_k?: number
}

export interface ChatAskResponse {
  answer: string
  sources: string[]
  context_count: number
  session_id: number
  message_id: number
  confidence?: string
  features?: {
    rerank_method?: string
    reranker_model?: string
  }
}

export interface SessionCreate {
  title: string
}

export interface SessionResponse {
  id: number
  user_id: number
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface MessageResponse {
  id: number
  session_id: number
  role: string
  content: string
  sources?: string[] | null
  feedback?: string | null
  created_at: string
}

export interface FeedbackRequest {
  feedback: 'up' | 'down'
}

export interface FeedbackResponse {
  message_id: number
  feedback: string
  success: boolean
}

export const chatApi = {
  ask: (data: ChatAskRequest) => {
    return api.post<ChatAskResponse>('/api/v1/chat/ask', data)
  },

  askStream: (data: ChatAskRequest, onChunk: (chunk: string) => void, onDone: (data: any) => void, onError: (error: string) => void, onVerification?: (data: any) => void) => {
    const token = sessionStorage.getItem('token')
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    
    fetch(`${baseURL}/api/v1/chat/ask/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ ...data, stream: true }),
    })
    .then((response) => {
      if (!response.ok) {
        if (response.status === 401) {
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('token_expiry')
          sessionStorage.removeItem('user')
          window.location.href = '/login'
          return
        }
        return response.json().then((err) => {
          throw new Error(err.detail || '请求失败')
        })
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法读取响应流')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            return
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const json = JSON.parse(line.slice(6))
                if (json.type === 'chunk') {
                  onChunk(json.content)
                } else if (json.type === 'done') {
                  onDone(json)
                } else if (json.type === 'error') {
                  onError(json.message)
                } else if (json.type === 'verification') {
                  onVerification?.(json)
                }
              } catch (e) {
                console.error('解析流式响应失败:', e)
              }
            }
          }

          read()
        })
      }

      read()
    })
    .catch((error) => {
      onError(error.message)
    })
  },

  getSessions: () => {
    return api.get<SessionResponse[]>('/api/v1/chat/sessions')
  },

  createSession: (data: SessionCreate) => {
    return api.post<SessionResponse>('/api/v1/chat/sessions', data)
  },

  getMessages: (sessionId: number) => {
    return api.get<MessageResponse[]>(`/api/v1/chat/sessions/${sessionId}/messages`)
  },

  submitFeedback: (messageId: number, data: FeedbackRequest) => {
    return api.post<FeedbackResponse>(`/api/v1/chat/messages/${messageId}/feedback`, data)
  },

  deleteSession: (sessionId: number) => {
    return api.delete(`/api/v1/chat/sessions/${sessionId}`)
  },

  getStats: () => {
    return api.get<{ totalDocuments: number; totalQuestions: number; satisfaction: number }>('/api/v1/chat/stats')
  },

  getQuickQuestions: (limit = 6) => {
    return api.get<string[]>('/api/v1/chat/quick-questions', { params: { limit } })
  },

  getModelInfo: () => {
    return api.get<{ model_name: string; provider: string }>('/api/v1/chat/model-info')
  },
}
