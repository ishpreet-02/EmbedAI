import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Bot } from 'lucide-react'
import { chatbotsAPI } from '../api/client'
import ChatbotCard from '../components/ChatbotCard'

export default function Dashboard() {
  const queryClient = useQueryClient()

  const { data: chatbots, isLoading, isError } = useQuery({
    queryKey: ['chatbots'],
    queryFn: () => chatbotsAPI.list().then((r) => r.data),
    refetchOnWindowFocus: true,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => chatbotsAPI.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chatbots'] }),
  })

  if (isLoading) {
    return (
      <div className="loading-center">
        <div className="spinner" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="alert-error" style={{ marginTop: 40 }}>
        Failed to load chatbots. Make sure your backend is running.
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Your chatbots</h1>
          <p className="page-subtitle">
            {chatbots?.length
              ? `${chatbots.length} chatbot${chatbots.length !== 1 ? 's' : ''}`
              : 'No chatbots yet'}
          </p>
        </div>
        <Link to="/chatbots/new" className="btn-primary">
          <Plus size={16} />
          New chatbot
        </Link>
      </div>

      {chatbots?.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <Bot size={24} />
          </div>
          <h2 className="empty-title">No chatbots yet</h2>
          <p className="empty-desc">
            Create your first chatbot by pasting a website URL.
            It'll be ready to answer questions in minutes.
          </p>
          <Link to="/chatbots/new" className="btn-primary">
            <Plus size={15} />
            Create your first chatbot
          </Link>
        </div>
      ) : (
        <div className="chatbot-grid">
          {chatbots?.map((chatbot) => (
            <ChatbotCard
              key={chatbot.id}
              chatbot={chatbot}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </>
  )
}
