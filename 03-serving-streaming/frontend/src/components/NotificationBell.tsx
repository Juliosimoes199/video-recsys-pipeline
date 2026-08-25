import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMarkAllNotificationsRead, useMarkNotificationRead, useNotifications } from '../hooks/useNotifications'
import { formatRelativeTime } from '../lib/format'

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { data } = useNotifications()
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()

  const items = data?.items ?? []
  const unreadCount = items.filter((n) => !n.read).length

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-full p-2 hover:bg-[var(--bg-hover)]"
        aria-label="Notificações"
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] shadow-xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-sm font-medium">Notificações</span>
              {unreadCount > 0 && (
                <button
                  onClick={() => markAllRead.mutate()}
                  className="text-xs text-[var(--accent)] hover:underline"
                >
                  Marcar tudo como lido
                </button>
              )}
            </div>
            <div className="max-h-96 overflow-y-auto">
              {items.length === 0 && (
                <p className="px-4 py-6 text-center text-sm text-[var(--text-muted)]">
                  Sem notificações por aqui.
                </p>
              )}
              {items.map((n) => (
                <Link
                  key={n.id}
                  to={n.videoId ? `/watch/${n.videoId}` : '#'}
                  onClick={() => {
                    if (!n.read) markRead.mutate(n.id)
                    setOpen(false)
                  }}
                  className={`block border-b border-[var(--border)] px-4 py-3 last:border-0 hover:bg-[var(--bg-hover)] ${
                    n.read ? 'opacity-60' : ''
                  }`}
                >
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">{n.body}</p>
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">{formatRelativeTime(n.createdAt)}</p>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function BellIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
