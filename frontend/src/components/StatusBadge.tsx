type Status = 'pending' | 'processing' | 'ready' | 'failed'

const config: Record<Status, { label: string; cls: string }> = {
  pending:    { label: 'Pending',    cls: 'badge-pending' },
  processing: { label: 'Processing', cls: 'badge-processing' },
  ready:      { label: 'Ready',      cls: 'badge-ready' },
  failed:     { label: 'Failed',     cls: 'badge-failed' },
}

export default function StatusBadge({ status }: { status: Status }) {
  const { label, cls } = config[status] ?? config.pending
  return <span className={`badge ${cls}`}>{label}</span>
}
