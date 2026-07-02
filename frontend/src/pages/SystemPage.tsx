import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Health } from '../api'
import { Button, Card } from '../components/ui'

type RowStatus = 'ok' | 'bad' | 'off'

function StatusRow({ name, status, detail }: { name: string; status: RowStatus; detail: string }) {
  const dot = status === 'ok' ? 'bg-heading' : status === 'bad' ? 'bg-accent' : 'bg-line'
  return (
    <div className="flex items-center justify-between border-b border-line pb-3 last:border-b-0 last:pb-0">
      <span className="font-heading text-sm font-bold text-ink">{name}</span>
      <span className="inline-flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <span className="text-sm">{detail}</span>
      </span>
    </div>
  )
}

export default function SystemPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(true)

  const check = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      setHealth(await api.health())
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
    <div>
      <h2 className="text-3xl">System Status</h2>
      <Card className="mt-8 max-w-md">
        <div className="space-y-3">
          <StatusRow name="Backend API" status={backend.status} detail={backend.detail} />
          <StatusRow name="Langfuse" status={langfuse.status} detail={langfuse.detail} />
        </div>
        <Button className="mt-6" onClick={() => void check()} disabled={loading}>
          {loading ? 'Checking…' : 'Check again'}
        </Button>
      </Card>
    </div>
  )
}
