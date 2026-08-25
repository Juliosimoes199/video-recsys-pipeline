import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <h1 className="text-2xl font-semibold">Página não encontrada</h1>
      <p className="text-sm text-[var(--text-muted)]">O que você procura não existe (ou foi removido).</p>
      <Link to="/" className="mt-2 rounded-full bg-[var(--bg-elevated)] px-4 py-2 text-sm hover:bg-[var(--bg-hover)]">
        Voltar para o início
      </Link>
    </div>
  )
}
