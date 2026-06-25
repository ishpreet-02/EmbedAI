import { useNavigate } from 'react-router-dom'
import { Globe, MessageSquare, Trash2 } from 'lucide-react'
import StatusBadge from './StatusBadge'
import type { Chatbot } from '../api/client'

interface Props {
  chatbot: Chatbot
  onDelete: (id: string) => void
}

export default function ChatbotCard({ chatbot, onDelete }: Props) {
  const navigate = useNavigate()

  const hostname = (() => {
    try { return new URL(chatbot.website_url).hostname }
    catch { return chatbot.website_url }
  })()

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm(`Delete "${chatbot.name}"? This cannot be undone.`)) {
      onDelete(chatbot.id)
    }
  }

  return (
    <div
      className={`chatbot-card${chatbot.status === 'processing' ? ' processing' : ''}`}
      onClick={() => navigate(`/chatbots/${chatbot.id}`)}
    >
      <div className="card-header">
        <div>
          <h3 className="card-title">{chatbot.name}</h3>
          <a
            href={chatbot.website_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="card-url"
          >
            <Globe size={12} />
            {hostname}
          </a>
        </div>
        <StatusBadge status={chatbot.status} />
      </div>

      <div className="card-stats">
        {chatbot.status === 'ready' && (
          <>
            <span>{chatbot.pages_indexed} pages</span>
            <span className="stat-divider">·</span>
            <span>{chatbot.chunks_stored} chunks</span>
          </>
        )}
        {chatbot.status === 'processing' && (
          <span className="processing-text">Building knowledge base…</span>
        )}
        {chatbot.status === 'pending' && (
          <span className="pending-text">Queued for scraping</span>
        )}
        {chatbot.status === 'failed' && (
          <span className="failed-text">Ingestion failed</span>
        )}
      </div>

      <div className="card-footer">
        <button
          className="card-conversations-btn"
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/chatbots/${chatbot.id}/conversations`)
          }}
        >
          <MessageSquare size={13} />
          Conversations
        </button>

        <button className="card-delete-btn" onClick={handleDelete} title="Delete chatbot">
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}
