import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Axios instance ────────────────────────────────────
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT to every request automatically
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirect to /login on 401 (expired / invalid token)
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

// ── Auth ──────────────────────────────────────────────
export const authAPI = {
  signup: (email: string, password: string) =>
    apiClient.post<{ access_token: string; user: { id: string; email: string } }>(
      '/api/auth/signup',
      { email, password },
    ),

  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; user: { id: string; email: string } }>(
      '/api/auth/login',
      { email, password },
    ),

  me: () =>
    apiClient.get<{ id: string; email: string; created_at: string }>('/api/auth/me'),
}

// ── Chatbots ──────────────────────────────────────────
export interface Chatbot {
  id: string
  name: string
  website_url: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
  qdrant_collection: string
  pages_indexed: number
  chunks_stored: number
  created_at: string
}

export const chatbotsAPI = {
  list: () => apiClient.get<Chatbot[]>('/api/chatbots'),

  get: (id: string) => apiClient.get<Chatbot>(`/api/chatbots/${id}`),

  create: (data: { name: string; website_url: string }) =>
    apiClient.post<Chatbot>('/api/chatbots', data),

  delete: (id: string) => apiClient.delete(`/api/chatbots/${id}`),

  getStatus: (id: string) =>
    apiClient.get<Pick<Chatbot, 'status' | 'pages_indexed' | 'chunks_stored'>>(
      `/api/chatbots/${id}/status`,
    ),

  getConversations: (id: string) =>
    apiClient.get<Conversation[]>(`/api/chatbots/${id}/conversations`),
}

// ── Conversations ─────────────────────────────────────
export interface Conversation {
  id: string
  chatbot_id: string
  visitor_id: string
  created_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export const conversationsAPI = {
  getMessages: (chatbotId: string, conversationId: string) =>
    apiClient.get<{ conversation_id: string; messages: Message[] }>(
      `/api/chat/${chatbotId}/history?conversation_id=${conversationId}`,
    ),
}

// Raw API base URL — used in TestChatPanel for streaming fetch
export const API_BASE = API_URL
