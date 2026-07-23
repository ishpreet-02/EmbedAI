import { Link, useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Globe, MessageSquare, FileText, Database, ExternalLink, RefreshCw } from 'lucide-react'
import { chatbotsAPI } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import EmbedCodeBox from '../components/EmbedCodeBox'
import TestChatPanel from '../components/TestChatPanel'
import AllowedOriginsSettings from '../components/AllowedOriginsSettings'
import WidgetCustomization from '../components/WidgetCustomization'

export default function ChatbotDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [resyncing, setResyncing] = useState(false)

  const { data: chatbot, isLoading, isError } = useQuery({
    queryKey: ['chatbot', id],
    queryFn: () => chatbotsAPI.get(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'processing' || s === 'pending' ? 5000 : false
    },
  })

  const resyncMutation = useMutation({
    mutationFn: () => chatbotsAPI.resync(id!),
    onSuccess: () => {
      setResyncing(true)
      queryClient.invalidateQueries({ queryKey: ['chatbot', id] })
      setTimeout(() => setResyncing(false), 1000)
    },
  })

  const hostname = (() => {
    try { return new URL(chatbot?.website_url ?? '').hostname }
    catch { return chatbot?.website_url ?? '' }
  })()

  if (isLoading) {
    return (
      <div className="loading-center">
        <div className="spinner" />
      </div>
    )
  }

  if (isError || !chatbot) {
    return (
      <div>
        <Link to="/dashboard" className="back-link"><ArrowLeft size={14} /> Dashboard</Link>
        <div className="alert-error">Chatbot not found or failed to load.</div>
      </div>
    )
  }

  return (
    <>
      {/* Header */}
      <Link to="/dashboard" className="back-link">
        <ArrowLeft size={14} />
        Dashboard
      </Link>

      <div className="chatbot-detail-header">
        <div className="chatbot-detail-title">
          <h1>{chatbot.name}</h1>
          <a
            href={chatbot.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="chatbot-detail-url"
          >
            <Globe size={13} />
            {hostname}
            <ExternalLink size={11} />
          </a>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn-secondary"
            onClick={() => resyncMutation.mutate()}
            disabled={resyncMutation.isPending || resyncing || chatbot.status === 'processing' || chatbot.status === 'pending'}
            title="Re-scrape the website and update the knowledge base"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}
          >
            <RefreshCw size={13} style={{ animation: (resyncMutation.isPending || chatbot.status === 'processing') ? 'spin 1s linear infinite' : 'none' }} />
            Resync
          </button>
          <StatusBadge status={chatbot.status} />
        </div>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Pages indexed</div>
          <div className="stat-value">{chatbot.pages_indexed ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Chunks stored</div>
          <div className="stat-value">{chatbot.chunks_stored ?? 0}</div>
        </div>
        <div className="stat-card"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate(`/chatbots/${id}/conversations`)}
        >
          <div className="stat-label">Conversations</div>
          <div className="stat-value" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <MessageSquare size={20} style={{ color: 'var(--primary)' }} />
            <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>View →</span>
          </div>
        </div>
      </div>

      {/* Not ready banner */}
      {chatbot.status !== 'ready' && (
        <div
          className="alert-error"
          style={{
            background: chatbot.status === 'failed' ? undefined : 'var(--warning-bg)',
            color: chatbot.status === 'failed' ? undefined : 'var(--warning-text)',
            border: chatbot.status === 'failed' ? undefined : '1px solid #FDE68A',
            marginBottom: 20,
          }}
        >
          {chatbot.status === 'processing' && 'Knowledge base is still building. Check back in a minute.'}
          {chatbot.status === 'pending' && 'This chatbot is queued for scraping. It will start shortly.'}
          {chatbot.status === 'failed' && 'Ingestion failed. Try deleting this chatbot and creating a new one.'}
        </div>
      )}

      {/* Two-column: embed code + test chat */}
      {chatbot.status === 'ready' && (
        <div className="detail-grid">
          <div>
            <div className="section">
              <h2 className="section-title">
                <FileText size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                Embed code
              </h2>
              <EmbedCodeBox chatbotId={chatbot.id} />
            </div>

            <AllowedOriginsSettings
              chatbotId={chatbot.id}
              allowedOrigins={chatbot.allowed_origins ?? []}
            />

            <WidgetCustomization chatbot={chatbot} />

            <div className="section">
              <h2 className="section-title">
                <Database size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                Knowledge base
              </h2>
              <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '0 0 4px' }}>
                {chatbot.pages_indexed} pages scraped · {chatbot.chunks_stored} text chunks embedded
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-subtle)', margin: 0 }}>
                Using <code style={{ fontFamily: 'monospace', fontSize: 12 }}>all-MiniLM-L6-v2</code> · Qdrant collection: <code style={{ fontFamily: 'monospace', fontSize: 12 }}>{chatbot.qdrant_collection}</code>
              </p>
            </div>
          </div>

          <div>
            <div className="section">
              <h2 className="section-title">Test your chatbot</h2>
              <TestChatPanel chatbot={chatbot} />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
