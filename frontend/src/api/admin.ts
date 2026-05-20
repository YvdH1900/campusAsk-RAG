import api from './request'

export interface DashboardStats {
  totalQuestions: number
  totalDocuments: number
  totalUsers: number
  satisfaction: number
}

export interface PopularQuestion {
  question: string
  count: number
}

export interface PaginatedUsersResponse {
  total: number
  page: number
  page_size: number
  pages: number
  items: UserInfo[]
}

export const adminApi = {
  getStats(): Promise<DashboardStats> {
    return api.get('/api/v1/admin/stats').then((res) => res.data)
  },

  getPopularQuestions(limit = 10): Promise<PopularQuestion[]> {
    return api.get('/api/v1/admin/popular-questions', { params: { limit } }).then((res) => res.data)
  },

  getUsers: (page = 1, pageSize = 10, role?: string) => {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (role) params.role = role
    return api.get<PaginatedUsersResponse>('/api/v1/admin/users', { params })
  },
}
