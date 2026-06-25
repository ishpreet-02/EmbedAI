import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { API_BASE } from '../api/client'

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
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return

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
        throw new Error(`HTTP ${res.status}`)
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
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: 'Something went wrong. Make sure your backend is running.',
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

      <div className="test-chat-messages">
        {messages.length === 0 && (
          <p className="chat-empty">Ask a question to test your chatbot</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            {msg.content || (msg.role === 'assistant' && streaming ? '…' : '')}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="test-chat-input">
        <input
          type="text"
          placeholder="Ask something…"
          value={input}
          disabled={streaming}
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
