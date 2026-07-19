import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Palette, Save, Check } from 'lucide-react'
import { chatbotsAPI, Chatbot } from '../api/client'

interface Props {
  chatbot: Chatbot
}

export default function WidgetCustomization({ chatbot }: Props) {
  const queryClient = useQueryClient()

  const [color, setColor] = useState(chatbot.widget_color ?? '#6366f1')
  const [header, setHeader] = useState(chatbot.widget_header ?? `${chatbot.name} AI`)
  const [welcome, setWelcome] = useState(
    chatbot.widget_welcome ??
      `Hi, I'm ${chatbot.name} AI, your AI Assistant from ${chatbot.name}. I noticed you were checking out our website. Are there any specific solutions or products you want to know more about?`,
  )
  const [position, setPosition] = useState<'left' | 'right'>(chatbot.widget_position ?? 'right')
  const [saved, setSaved] = useState(false)

  const mutation = useMutation({
    mutationFn: () =>
      chatbotsAPI.update(chatbot.id, {
        widget_color: color,
        widget_header: header,
        widget_welcome: welcome,
        widget_position: position,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatbot', chatbot.id] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  return (
    <div className="section">
      <h2 className="section-title">
        <Palette size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Widget customization
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Color */}
        <label style={{ fontSize: 13, fontWeight: 500 }}>
          Brand color
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              style={{ width: 40, height: 32, border: 'none', borderRadius: 6, cursor: 'pointer', padding: 2 }}
            />
            <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{color}</span>
          </div>
        </label>

        {/* AI name */}
        <label style={{ fontSize: 13, fontWeight: 500 }}>
          AI name
          <input
            type="text"
            value={header}
            onChange={(e) => setHeader(e.target.value)}
            maxLength={60}
            placeholder={`${chatbot.name} AI`}
            style={{
              display: 'block', width: '100%', marginTop: 6,
              padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)',
              background: 'var(--input-bg)', color: 'var(--text)', fontSize: 13,
              boxSizing: 'border-box',
            }}
          />
        </label>

        {/* Welcome message */}
        <label style={{ fontSize: 13, fontWeight: 500 }}>
          Welcome message
          <textarea
            value={welcome}
            onChange={(e) => setWelcome(e.target.value)}
            maxLength={300}
            rows={4}
            placeholder={`Hi, I'm ${chatbot.name} AI, your AI Assistant from ${chatbot.name}. I noticed you were checking out our website. Are there any specific solutions or products you want to know more about?`}
            style={{
              display: 'block', width: '100%', marginTop: 6,
              padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)',
              background: 'var(--input-bg)', color: 'var(--text)', fontSize: 13,
              boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.5,
            }}
          />
        </label>

        {/* Position */}
        <label style={{ fontSize: 13, fontWeight: 500 }}>
          Chat bubble position
          <div style={{ display: 'flex', gap: 10, marginTop: 6 }}>
            {(['right', 'left'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPosition(p)}
                style={{
                  padding: '6px 16px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
                  border: position === p ? '2px solid var(--primary)' : '1px solid var(--border)',
                  background: position === p ? 'var(--primary-subtle)' : 'var(--input-bg)',
                  color: position === p ? 'var(--primary)' : 'var(--text-muted)',
                  fontWeight: position === p ? 600 : 400,
                }}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </label>

        <button
          className="btn-primary"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {saved ? <><Check size={14} /> Saved!</> : <><Save size={14} /> Save settings</>}
        </button>
      </div>
    </div>
  )
}
