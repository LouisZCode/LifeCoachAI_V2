import { NavLink, Outlet } from 'react-router-dom'

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `block rounded-lg px-3 py-2 font-heading text-sm font-bold transition-colors ${
          isActive
            ? 'bg-parchment/15 text-parchment'
            : 'text-parchment/70 hover:bg-parchment/10 hover:text-parchment'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col justify-between bg-brand p-6">
        <div>
          <h1 className="text-2xl text-parchment">LifeCoach AI</h1>
          <p className="mt-1 font-heading text-xs uppercase tracking-widest text-parchment/60">
            Version 2
          </p>
          <nav className="mt-8 space-y-1">
            <NavItem to="/clients" label="Clients" />
            <NavItem to="/system" label="System" />
          </nav>
        </div>
        <p className="italic text-parchment/90">“Your Path, Your Power”</p>
      </aside>

      <main className="flex-1 overflow-y-auto p-10">
        <Outlet />
      </main>
    </div>
  )
}
