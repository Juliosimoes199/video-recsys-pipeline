import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/clerk-react'
import { NotificationBell } from './NotificationBell'

export function Navbar() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    navigate(query.trim() ? `/?q=${encodeURIComponent(query.trim())}` : '/')
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--bg)] px-4">
      <Link to="/" className="flex shrink-0 items-center gap-1 text-lg font-semibold tracking-tight">
        <span className="text-red-600">▶</span> Tube
      </Link>

      <form onSubmit={handleSearch} className="hidden max-w-xl flex-1 sm:flex">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Pesquisar"
          className="w-full rounded-l-full border border-[var(--border)] bg-transparent px-4 py-1.5 text-sm outline-none focus:border-[var(--accent)]"
        />
        <button
          type="submit"
          className="rounded-r-full border border-l-0 border-[var(--border)] bg-[var(--bg-elevated)] px-4 hover:bg-[var(--bg-hover)]"
          aria-label="Pesquisar"
        >
          🔍
        </button>
      </form>

      <div className="flex shrink-0 items-center gap-2">
        <SignedIn>
          {import.meta.env.VITE_UPLOAD_ENABLED === 'true' && (
            <>
              <Link
                to="/upload"
                className="hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-sm hover:bg-[var(--bg-hover)] sm:flex"
              >
                <span aria-hidden>⬆️</span> Enviar
              </Link>
              <Link to="/studio" className="hidden rounded-full px-3 py-1.5 text-sm hover:bg-[var(--bg-hover)] sm:flex">
                Seus vídeos
              </Link>
            </>
          )}
          <NotificationBell />
          <UserButton afterSignOutUrl="/" />
        </SignedIn>
        <SignedOut>
          <SignInButton mode="modal">
            <button className="flex items-center gap-1.5 rounded-full border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--accent)] hover:bg-[var(--bg-hover)]">
              Entrar
            </button>
          </SignInButton>
        </SignedOut>
      </div>
    </header>
  )
}
