import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Save } from 'lucide-react'
import { chatbotsAPI } from '../api/client'

interface Props {
  chatbotId: string
  allowedOrigins: string[]
}

export default function AllowedOriginsSettings({ chatbotId, allowedOrigins }: Props) {
  const queryClient = useQueryClient()
  const [text, setText] = useState(allowedOrigins.join('\n'))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setText(allowedOrigins.join('\n'))
  }, [allowedOrigins])

  const saveMutation = useMutation({
    mutationFn: (origins: string[]) =>
      chatbotsAPI.update(chatbotId, { allowed_origins: origins }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatbot', chatbotId] })
      setError(null)
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string | { msg: string }[] } } })
          .response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(', '))
      } else {
        setError('Failed to save allowed origins')
      }
    },
  })

  const parsedOrigins = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  const dirty = JSON.stringify(parsedOrigins) !== JSON.stringify(allowedOrigins)

  const handleSave = () => {
    saveMutation.mutate(parsedOrigins)
  }

  return (
    <div className="section">
      <h2 className="section-title">
        <Shield size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Allowed domains
      </h2>
      <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '0 0 12px' }}>
        Only these origins can embed and use your chatbot widget. One domain per line
        (e.g. <code style={{ fontFamily: 'monospace', fontSize: 12 }}>https://example.com</code>).
        Leave empty to allow any domain.
      </p>
      <textarea
        className="form-input"
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={'https://yourdomain.com\nhttps://www.yourdomain.com'}
        spellCheck={false}
        style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 13 }}
      />
      {error && <p className="form-error" style={{ marginTop: 8 }}>{error}</p>}
      <button
        type="button"
        className="btn-primary"
        onClick={handleSave}
        disabled={saveMutation.isPending || !dirty}
        style={{ marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 6 }}
      >
        <Save size={14} />
        {saveMutation.isPending ? 'Saving…' : 'Save domains'}
      </button>
      {saveMutation.isSuccess && !dirty && (
        <span style={{ marginLeft: 12, fontSize: 13, color: 'var(--success-text)' }}>
          Saved
        </span>
      )}
    </div>
  )
}
