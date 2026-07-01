import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { API_BASE } from '../api/client'

const MAX_MESSAGE_LENGTH = 1000

interface Msg {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  chatbotId: string
  chatbotName: string
}

export default function TestChatPanel({ chatbotId, chatbotName }: Props) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Scroll only the messages box — NOT the whole page
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    if (text.length > MAX_MESSAGE_LENGTH) return

    setInput('')

    // Append user message, then an empty assistant placeholder
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '' },
    ])
    setStreaming(true)

    try {
      const res = await fetch(`${API_BASE}/api/chat/${chatbotId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const detail = err.detail
        const message =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg).join(', ')
              : `HTTP ${res.status}`
        throw new Error(message)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()

      // Stream tokens into the last assistant message
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const token = decoder.decode(value, { stream: true })
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: updated[updated.length - 1].content + token,
          }
          return updated
        })
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Something went wrong.'
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: message,
        }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div className="test-chat">
      <div className="test-chat-header">
        <span className="chat-dot" />
        {chatbotName}
      </div>

      <div className="test-chat-messages" ref={messagesRef}>
        {messages.length === 0 && (
          <p className="chat-empty">Ask a question to test your chatbot</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            {msg.content || (msg.role === 'assistant' && streaming ? '…' : '')}
          </div>
        ))}
      </div>

      <div className="test-chat-input">
        <input
          type="text"
          placeholder="Ask something…"
          value={input}
          disabled={streaming}
          maxLength={MAX_MESSAGE_LENGTH}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button onClick={send} disabled={streaming || !input.trim()}>
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}
