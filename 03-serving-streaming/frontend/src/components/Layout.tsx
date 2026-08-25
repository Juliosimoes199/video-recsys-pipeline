import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'

export function Layout() {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <Navbar />
      <main className="mx-auto max-w-[1800px] px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
