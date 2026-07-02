import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatDate } from '../api'
import type { Client } from '../api'
import { Button, Card, ErrorNote, Field, Input } from '../components/ui'

function NewClientForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!name.trim()) {
      setError('Name is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.createClient({ name: name.trim(), email: email.trim() || null })
      setName('')
      setEmail('')
      onCreated()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create client.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mt-6 max-w-md">
      <h3 className="text-lg">New client</h3>
      <div className="mt-4 space-y-3">
        <Field label="Name">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full name"
            autoFocus
          />
        </Field>
        <Field label="Email (optional)">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
          />
        </Field>
      </div>
      <ErrorNote message={error} />
      <Button className="mt-4" onClick={() => void submit()} disabled={saving}>
        {saving ? 'Saving…' : 'Create client'}
      </Button>
    </Card>
  )
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    try {
      setClients(await api.listClients())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load clients.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-3xl">Clients</h2>
        <Button variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : '+ New client'}
        </Button>
      </div>

      {showForm && (
        <NewClientForm
          onCreated={() => {
            setShowForm(false)
            void load()
          }}
        />
      )}

      <ErrorNote message={error} />

      {clients && clients.length === 0 && !showForm && (
        <p className="mt-8 max-w-xl">
          No clients yet. Create the first one to start tracking sessions.
        </p>
      )}

      <div className="mt-8 grid max-w-4xl grid-cols-1 gap-4 md:grid-cols-2">
        {clients?.map((client) => (
          <Link key={client.id} to={`/clients/${client.id}`}>
            <Card className="transition-shadow hover:shadow-lg">
              <h3 className="text-lg">{client.name}</h3>
              <p className="mt-1 text-sm text-ink/70">{client.email ?? 'No email'}</p>
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="font-heading font-bold text-accent">
                  {client.session_count} session{client.session_count === 1 ? '' : 's'}
                </span>
                <span className="text-ink/50">since {formatDate(client.created_at)}</span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
