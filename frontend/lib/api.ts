import axios from 'axios'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

// Create axios instance with default config
const axiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor to include auth token
axiosInstance.interceptors.request.use(
  (config) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Add response interceptor to handle errors
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth on 401
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('user')
        window.dispatchEvent(new Event('auth:logout'))
      }
    }
    return Promise.reject(error)
  }
)

class ApiClient {
  isAuthenticated(): boolean {
    if (typeof window === 'undefined') return false
    const token = localStorage.getItem('auth_token')
    return !!token
  }

  async verifyToken() {
    const response = await axiosInstance.get('/api/auth/verify')
    return response.data
  }

  logout() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
      window.dispatchEvent(new Event('auth:logout'))
    }
  }

  // Bot control
  async getBotStatus() {
    const response = await axiosInstance.get('/api/bot/status')
    return response.data
  }

  async startBot(settings?: any) {
    const response = await axiosInstance.post('/api/bot/start', settings || {})
    return response.data
  }

  async stopBot() {
    const response = await axiosInstance.post('/api/bot/stop')
    return response.data
  }

  async pauseBot() {
    const response = await axiosInstance.post('/api/bot/pause')
    return response.data
  }

  async resumeBot() {
    const response = await axiosInstance.post('/api/bot/resume')
    return response.data
  }

  // Settings
  async getSettings() {
    const response = await axiosInstance.get('/api/settings')
    return response.data
  }

  async updateSettings(settings: any) {
    const response = await axiosInstance.post('/api/settings', settings)
    return response.data
  }

  // Jobs
  async getJobs() {
    const response = await axiosInstance.get('/api/jobs')
    return response.data
  }

  async markJobAsRead(jobId: string) {
    const response = await axiosInstance.post(`/api/jobs/${jobId}/mark-read`)
    return response.data
  }

  // Bidding
  async generateBid(data: { jobId: string; promptIndex?: number; model?: string }) {
    const response = await axiosInstance.post(`/api/bidding/generate/${data.jobId}`, {
      prompt_index: data.promptIndex,
      model: data.model,
    })
    return response.data
  }

  async analyzeJob(jobId: string) {
    const response = await axiosInstance.post(`/api/bidding/analyze/${jobId}`)
    return response.data
  }

  // Auto-bid
  async testAutoBidBackend() {
    const response = await axiosInstance.get('/api/auto-bid/test')
    return response.data
  }

  async submitAutoBid(jobId: string, promptIndex: number, jobUrl: string, bidContent: string) {
    const response = await axiosInstance.post('/api/auto-bid/submit', {
      job_id: jobId,
      prompt_index: promptIndex,
      job_url: jobUrl,
      bid_content: bidContent,
    })
    return response.data
  }

  // Favorites
  async getFavorites() {
    const response = await axiosInstance.get('/api/favorites')
    return response.data
  }

  async addFavorite(employerId: string, employerName?: string, employerDisplayName?: string, avatarUrl?: string, profileUrl?: string) {
    const response = await axiosInstance.post('/api/favorites', {
      employer_id: employerId,
      employer_name: employerName,
      employer_display_name: employerDisplayName,
      avatar_url: avatarUrl,
      profile_url: profileUrl,
    })
    return response.data
  }

  async removeFavorite(favoriteId: number) {
    const response = await axiosInstance.delete(`/api/favorites/${favoriteId}`)
    return response.data
  }

  // Blocked users
  async getBlocked() {
    const response = await axiosInstance.get('/api/blocked')
    return response.data
  }

  async addBlocked(employerId?: string, clientUsername?: string, employerName?: string, employerDisplayName?: string, avatarUrl?: string, profileUrl?: string) {
    const response = await axiosInstance.post('/api/blocked', {
      employer_id: employerId,
      client_username: clientUsername,
      employer_name: employerName,
      employer_display_name: employerDisplayName,
      avatar_url: avatarUrl,
      profile_url: profileUrl,
    })
    return response.data
  }

  async removeBlocked(blockedId: number) {
    const response = await axiosInstance.delete(`/api/blocked/${blockedId}`)
    return response.data
  }

  // Profile
  async getProfile() {
    const response = await axiosInstance.get('/api/profile')
    return response.data
  }

  async updateProfile(data: { email?: string; displayName?: string }) {
    const response = await axiosInstance.post('/api/profile', data)
    return response.data
  }

  async changePassword(oldPassword: string, newPassword: string) {
    const response = await axiosInstance.post('/api/profile/password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
    return response.data
  }

  // Data management
  async clearBids() {
    const response = await axiosInstance.post('/api/data/clear-bids')
    return response.data
  }

  async clearJobs() {
    const response = await axiosInstance.post('/api/data/clear-jobs')
    return response.data
  }

  // Notifications
  async getNotificationSettings() {
    const response = await axiosInstance.get('/api/notifications/settings')
    return response.data
  }

  async updateNotificationSettings(settings: any) {
    const response = await axiosInstance.post('/api/notifications/settings', settings)
    return response.data
  }

  async testTelegram() {
    const response = await axiosInstance.post('/api/notifications/test/telegram')
    return response.data
  }

  async testDiscord() {
    const response = await axiosInstance.post('/api/notifications/test/discord')
    return response.data
  }
}

export const apiClient = new ApiClient()
