import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { API_BASE } from '../api/client'

export default function EmbedCodeBox({ chatbotId }: { chatbotId: string }) {
  const [copied, setCopied] = useState(false)
  const snippet = `<script src="${API_BASE}/widget.js" data-id="${chatbotId}"></script>`

  const copy = async () => {
    await navigator.clipboard.writeText(snippet)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="embed-box">
      <div className="embed-header">
        <span>Embed on your website</span>
        <button className="copy-btn" onClick={copy}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="embed-code">{snippet}</pre>
      <p className="embed-hint">
        Paste this one line before the <code>&lt;/body&gt;</code> tag on your website.
        The chat bubble appears instantly.
      </p>
    </div>
  )
}
