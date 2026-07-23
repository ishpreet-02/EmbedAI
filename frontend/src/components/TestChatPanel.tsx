import { useState, useRef, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { Bot, Send } from 'lucide-react'
import { API_BASE, Chatbot } from '../api/client'

const MAX_MESSAGE_LENGTH = 1000

interface Msg {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  chatbot: Chatbot
}

export default function TestChatPanel({ chatbot }: Props) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [visitorId, setVisitorId] = useState<string | null>(
    () => localStorage.getItem(`chatbot_test_visitor_id_${chatbot.id}`),
  )
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  const color = chatbot.widget_color || '#6366f1'
  const header = chatbot.widget_header || `${chatbot.name} AI`
  const welcome =
    chatbot.widget_welcome ||
    `Hi, I'm ${header}, your AI Assistant from ${chatbot.name}. I noticed you were checking out our website. Are there any specific solutions or products you want to know more about?`

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
      const payload: {
        message: string
        visitor_id?: string
        conversation_id?: string
      } = { message: text }

      if (visitorId) payload.visitor_id = visitorId
      if (conversationId) payload.conversation_id = conversationId

      const token = localStorage.getItem('token')
      if (!token) throw new Error('You must be logged in to test this chatbot.')

      const res = await fetch(`${API_BASE}/api/chat/${chatbot.id}/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
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

      const newVisitorId = res.headers.get('X-Visitor-Id')
      if (newVisitorId) {
        setVisitorId(newVisitorId)
        localStorage.setItem(`chatbot_test_visitor_id_${chatbot.id}`, newVisitorId)
      }

      const newConversationId = res.headers.get('X-Conversation-Id')
      if (newConversationId) setConversationId(newConversationId)

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
    <div
      className="test-chat"
      style={{ '--test-chat-color': color } as CSSProperties}
    >
      <div className="test-chat-header">
        <div className="test-chat-avatar">
          <Bot size={18} />
        </div>
        <div className="test-chat-heading">
          <div className="test-chat-title">{header}</div>
          <div className="test-chat-subtitle">Ask me anything about this site</div>
        </div>
      </div>

      <div className="test-chat-messages" ref={messagesRef}>
        <div className="chat-msg assistant">{welcome}</div>
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

      <div className="test-chat-powered">
        Powered by <span>EmbedAI</span>
      </div>
    </div>
  )
}
