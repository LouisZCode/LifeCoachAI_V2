import { useCallback, useEffect, useState } from 'react'

type Health = {
  status: string
  app: string
  version: string
  langfuse: { configured: boolean; connected: boolean }
}

type RowStatus = 'ok' | 'bad' | 'off'

function StatusRow({ name, status, detail }: { name: string; status: RowStatus; detail: string }) {
  const dot =
    status === 'ok' ? 'bg-heading' : status === 'bad' ? 'bg-accent' : 'bg-line'
  return (
    <div className="flex items-center justify-between border-b border-line pb-3 last:border-b-0 last:pb-0">
      <span className="font-heading font-bold text-sm text-ink">{name}</span>
      <span className="inline-flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <span className="text-sm">{detail}</span>
      </span>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(true)

  const check = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      const res = await fetch('/api/health')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setHealth((await res.json()) as Health)
    } catch {
      setHealth(null)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void check()
  }, [check])

  const backend: { status: RowStatus; detail: string } = failed
    ? { status: 'bad', detail: 'unreachable' }
    : health?.status === 'ok'
      ? { status: 'ok', detail: `ok — v${health.version}` }
      : { status: 'off', detail: 'checking…' }

  const langfuse: { status: RowStatus; detail: string } = !health
    ? { status: 'off', detail: '—' }
    : !health.langfuse.configured
      ? { status: 'off', detail: 'not configured' }
      : health.langfuse.connected
        ? { status: 'ok', detail: 'connected' }
        : { status: 'bad', detail: 'keys set, not reachable' }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col justify-between bg-brand p-6">
        <div>
          <h1 className="text-2xl text-parchment">LifeCoach AI</h1>
          <p className="mt-1 font-heading text-xs uppercase tracking-widest text-parchment/60">
            Version 2
          </p>
        </div>
        <p className="italic text-parchment/90">“Your Path, Your Power”</p>
      </aside>

      <main className="flex-1 p-10">
        <h2 className="text-3xl">Welcome</h2>
        <p className="mt-2 max-w-xl">
          Phase 0 scaffold — the pieces below prove the stack is wired end to end.
        </p>

        <section className="mt-8 max-w-md rounded-[15px] border border-accent bg-cream p-6 shadow-md">
          <h3 className="text-lg">System Status</h3>
          <div className="mt-4 space-y-3">
            <StatusRow name="Backend API" status={backend.status} detail={backend.detail} />
            <StatusRow name="Langfuse" status={langfuse.status} detail={langfuse.detail} />
          </div>
          <button
            type="button"
            onClick={() => void check()}
            disabled={loading}
            className="mt-6 rounded-lg bg-accent px-4 py-2 font-heading font-bold text-white transition-colors hover:bg-accent-dark disabled:opacity-60"
          >
            {loading ? 'Checking…' : 'Check again'}
          </button>
        </section>
      </main>
    </div>
  )
}
