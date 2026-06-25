import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, MessageSquare } from 'lucide-react'
import { chatbotsAPI, conversationsAPI } from '../api/client'
import type { Conversation } from '../api/client'

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function Conversations() {
  const { id: chatbotId } = useParams<{ id: string }>()
  const [selected, setSelected] = useState<Conversation | null>(null)

  const { data: chatbot } = useQuery({
    queryKey: ['chatbot', chatbotId],
    queryFn: () => chatbotsAPI.get(chatbotId!).then((r) => r.data),
    enabled: !!chatbotId,
  })

  const { data: conversations, isLoading: loadingConvs } = useQuery({
    queryKey: ['conversations', chatbotId],
    queryFn: () => chatbotsAPI.getConversations(chatbotId!).then((r) => r.data),
    enabled: !!chatbotId,
  })

  const { data: thread, isLoading: loadingThread } = useQuery({
    queryKey: ['messages', chatbotId, selected?.id],
    queryFn: () =>
      conversationsAPI.getMessages(chatbotId!, selected!.id).then((r) => r.data),
    enabled: !!selected,
  })

  return (
    <>
      <div className="page-header">
        <div>
          <Link to={`/chatbots/${chatbotId}`} className="back-link" style={{ marginBottom: 4 }}>
            <ArrowLeft size={14} />
            {chatbot?.name ?? 'Chatbot'}
          </Link>
          <h1 className="page-title">Conversations</h1>
          <p className="page-subtitle">
            {conversations?.length ?? 0} conversation{conversations?.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <div className="conversations-layout">
        {/* Left: conversation list */}
        <div className="conv-list">
          <div className="conv-list-header">Visitors</div>

          {loadingConvs && (
            <div className="loading-center"><div className="spinner" /></div>
          )}

          {!loadingConvs && conversations?.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
              No conversations yet. Visitors will appear here once they use your chatbot.
            </div>
          )}

          {conversations?.map((conv) => (
            <div
              key={conv.id}
              className={`conv-item${selected?.id === conv.id ? ' active' : ''}`}
              onClick={() => setSelected(conv)}
            >
              <div className="conv-visitor">{conv.visitor_id}</div>
              <div className="conv-time">{formatTime(conv.created_at)}</div>
            </div>
          ))}
        </div>

        {/* Right: message thread */}
        <div className="conv-messages">
          <div className="conv-messages-header">
            {selected
              ? `Conversation with ${selected.visitor_id}`
              : 'Select a conversation to view messages'}
          </div>

          <div className="conv-messages-body">
            {!selected && (
              <div className="conv-empty">
                <MessageSquare size={18} style={{ marginRight: 8, opacity: 0.4 }} />
                Select a conversation on the left
              </div>
            )}

            {loadingThread && (
              <div className="loading-center"><div className="spinner" /></div>
            )}

            {thread?.messages.map((msg) => (
              <div key={msg.id} className={`chat-msg ${msg.role}`}>
                {msg.content}
              </div>
            ))}

            {selected && thread?.messages.length === 0 && (
              <div className="conv-empty">No messages in this conversation</div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
