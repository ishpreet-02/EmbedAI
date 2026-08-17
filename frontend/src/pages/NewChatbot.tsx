import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Globe, Loader2, CheckCircle, XCircle } from 'lucide-react'
import type { AxiosError } from 'axios'
import { chatbotsAPI } from '../api/client'

type Phase = 'form' | 'polling' | 'done' | 'failed'

const POLL_INTERVAL_MS = 3000

const statusLabel: Record<string, string> = {
  pending:    'Queued for scraping…',
  processing: 'Building knowledge base…',
  ready:      'Your chatbot is ready!',
  failed:     'Ingestion failed.',
}

export default function NewChatbot() {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [phase, setPhase] = useState<Phase>('form')
  const [chatbotId, setChatbotId] = useState('')
  const [statusText, setStatusText] = useState('')
  const navigate = useNavigate()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Clean up polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const startPolling = (id: string) => {
    setPhase('polling')
    setStatusText('pending')

    pollRef.current = setInterval(async () => {
      try {
        const res = await chatbotsAPI.getStatus(id)
        const { status } = res.data
        setStatusText(status)

        if (status === 'ready') {
          clearInterval(pollRef.current!)
          setPhase('done')
        } else if (status === 'failed') {
          clearInterval(pollRef.current!)
          setPhase('failed')
        }
      } catch {
        // Backend might be briefly unavailable during processing — just keep polling
      }
    }, POLL_INTERVAL_MS)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Basic URL validation
    try { new URL(url) } catch {
      setError('Please enter a valid URL including https://')
      return
    }

    setLoading(true)
    try {
      const res = await chatbotsAPI.create({ name, website_url: url })
      setChatbotId(res.data.id)
      startPolling(res.data.id)
    } catch (err: unknown) {
      const msg =
        (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
        ?? 'Failed to create chatbot. Please try again.'
      setError(msg)
      setLoading(false)
    }
  }

  // ── Polling / progress view ───────────────────────────
  if (phase === 'polling' || phase === 'done' || phase === 'failed') {
    return (
      <>
        <div className="page-header">
          <h1 className="page-title">
            {phase === 'polling' ? 'Setting up your chatbot' : phase === 'done' ? 'Chatbot ready!' : 'Setup failed'}
          </h1>
        </div>

        <div className="progress-card" style={{ maxWidth: 480 }}>
          <div className="progress-icon">
            {phase === 'polling' && <Loader2 size={26} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />}
            {phase === 'done' && <CheckCircle size={26} style={{ color: 'var(--success-dot)' }} />}
            {phase === 'failed' && <XCircle size={26} style={{ color: 'var(--danger-dot)' }} />}
          </div>

          <h2 className="progress-title">
            {phase === 'polling' && statusLabel[statusText]}
            {phase === 'done' && 'Your chatbot is ready!'}
            {phase === 'failed' && 'Something went wrong'}
          </h2>

          <p className="progress-desc">
            {phase === 'polling' && 'Hang tight — we\'re scraping your website and building the AI knowledge base.'}
            {phase === 'done' && 'Your chatbot has been trained on your website content. Copy the embed code and add it to your site.'}
            {phase === 'failed' && 'The ingestion pipeline failed. This can happen with sites that block crawlers. You can try again with a different URL.'}
          </p>

          {phase === 'polling' && (
            <div className="progress-bar-track">
              <div className="progress-bar-fill" />
            </div>
          )}

          {phase === 'done' && (
            <button
              className="btn-primary"
              style={{ margin: '0 auto' }}
              onClick={() => navigate(`/chatbots/${chatbotId}`)}
            >
              View chatbot →
            </button>
          )}

          {phase === 'failed' && (
            <button
              className="btn-secondary"
              style={{ margin: '0 auto' }}
              onClick={() => {
                setPhase('form')
                setLoading(false)
              }}
            >
              Try again
            </button>
          )}
        </div>
      </>
    )
  }

  // ── Form view ─────────────────────────────────────────
  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">New chatbot</h1>
          <p className="page-subtitle">Paste your website URL — we'll handle the rest</p>
        </div>
      </div>

      <div style={{ maxWidth: 480 }}>
        {error && <div className="form-error">{error}</div>}

        <div className="section">
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Company or chatbot name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. DDN"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
              />
              <p className="form-hint">
                Used to create the default AI name and first message. You can edit both later.
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Website URL</label>
              <div style={{ position: 'relative' }}>
                <Globe
                  size={16}
                  style={{
                    position: 'absolute',
                    left: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type="url"
                  className="form-input"
                  placeholder="https://example.com"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  style={{ paddingLeft: 36 }}
                />
              </div>
              <p className="form-hint">
                We'll crawl up to 20 pages automatically, including subpages.
              </p>
            </div>

            <button
              type="submit"
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
              disabled={loading}
            >
              {loading ? 'Creating…' : 'Create chatbot'}
            </button>
          </form>
        </div>
      </div>
    </>
  )
}
