import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, MessageSquare, User } from 'lucide-react'
import { chatbotsAPI, conversationsAPI } from '../api/client'
import type { Conversation } from '../api/client'

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** Turn "visitor_a3b7f2c1" → "Visitor #A3B7" for readability */
function formatVisitorLabel(visitor_id: string): string {
  // Strip common prefixes (visitor_, dashboard_test_, etc.)
  const clean = visitor_id.replace(/^(visitor_|dashboard_test_|tester_)/, '')
  // Uppercase and take first 6 chars
  const short = clean.slice(0, 6).toUpperCase()
  return `Visitor #${short}`
}

/** True if this is a dashboard test session — label it differently */
function isTestSession(visitor_id: string): boolean {
  return visitor_id.startsWith('dashboard_test_')
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

  const totalMessages = conversations?.reduce(
    (sum, c) => sum + (c.message_count ?? 0), 0
  ) ?? 0

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
            {totalMessages > 0 && (
              <span style={{ marginLeft: 8, color: 'var(--text-subtle)' }}>
                · {totalMessages} messages total
              </span>
            )}
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
              {/* Top row: visitor label + message count badge */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                  {/* Icon: test sessions get a different colour */}
                  <div style={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    background: isTestSession(conv.visitor_id)
                      ? 'var(--accent-light)'
                      : 'var(--primary-light)',
                    color: isTestSession(conv.visitor_id)
                      ? 'var(--accent)'
                      : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <User size={13} />
                  </div>

                  <span className="conv-visitor" style={{ fontSize: 12 }}>
                    {isTestSession(conv.visitor_id)
                      ? 'Dashboard Test'
                      : formatVisitorLabel(conv.visitor_id)}
                  </span>
                </div>

                {/* Message count pill */}
                {(conv.message_count ?? 0) > 0 && (
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                    padding: '2px 7px',
                    background: 'var(--border-light)',
                    color: 'var(--text-muted)',
                    borderRadius: 20,
                    fontSize: 11,
                    fontWeight: 500,
                    flexShrink: 0,
                  }}>
                    <MessageSquare size={10} />
                    {conv.message_count}
                  </span>
                )}
              </div>

              {/* Bottom row: timestamp */}
              <div className="conv-time" style={{ marginLeft: 32 }}>
                {formatTime(conv.created_at)}
              </div>
            </div>
          ))}
        </div>

        {/* Right: message thread */}
        <div className="conv-messages">
          <div className="conv-messages-header">
            {selected
              ? (
                <span>
                  {isTestSession(selected.visitor_id)
                    ? 'Dashboard Test Session'
                    : formatVisitorLabel(selected.visitor_id)}
                  {(selected.message_count ?? 0) > 0 && (
                    <span style={{ marginLeft: 8, color: 'var(--text-subtle)', fontWeight: 400, fontSize: 12 }}>
                      {selected.message_count} message{selected.message_count !== 1 ? 's' : ''}
                    </span>
                  )}
                </span>
              )
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

            {selected && !loadingThread && thread?.messages.length === 0 && (
              <div className="conv-empty">No messages in this conversation</div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
