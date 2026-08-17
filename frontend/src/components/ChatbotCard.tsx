import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Globe, MessageSquare, Trash2, AlertTriangle, X } from 'lucide-react'
import StatusBadge from './StatusBadge'
import type { Chatbot } from '../api/client'

interface Props {
  chatbot: Chatbot
  onDelete: (id: string) => void
}

export default function ChatbotCard({ chatbot, onDelete }: Props) {
  const navigate = useNavigate()
  // When true, the card footer flips into a confirm-before-delete state
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const hostname = (() => {
    try { return new URL(chatbot.website_url).hostname }
    catch { return chatbot.website_url }
  })()

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setConfirmingDelete(true)
  }

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete(chatbot.id)
  }

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    setConfirmingDelete(false)
  }

  return (
    <div
      className={`chatbot-card${chatbot.status === 'processing' ? ' processing' : ''}`}
      onClick={() => !confirmingDelete && navigate(`/chatbots/${chatbot.id}`)}
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

      {/* Footer: normal view OR delete confirmation inline */}
      {!confirmingDelete ? (
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

          <button
            className="card-delete-btn"
            onClick={handleDeleteClick}
            title="Delete chatbot"
          >
            <Trash2 size={13} />
          </button>
        </div>
      ) : (
        /* ── Inline delete confirmation ── */
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            padding: '8px 10px',
            background: 'var(--danger-bg)',
            border: '1px solid #FECACA',
            borderRadius: 'var(--radius)',
            marginTop: 2,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
            color: 'var(--danger-text)',
            fontWeight: 500,
          }}>
            <AlertTriangle size={13} />
            Delete forever?
          </span>

          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={handleCancelDelete}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--surface)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              <X size={11} />
              Cancel
            </button>
            <button
              onClick={handleConfirmDelete}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                fontSize: 12,
                fontWeight: 500,
                background: '#EF4444',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              <Trash2 size={11} />
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
