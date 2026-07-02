import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, formatDate } from '../api'
import type { ClientDetail, Session } from '../api'
import { Button, Card, ConfirmButton, ErrorNote, Field, Input, TextArea } from '../components/ui'

function todayISO(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function EditClientForm({
  client,
  onSaved,
  onCancel,
}: {
  client: ClientDetail
  onSaved: () => void
  onCancel: () => void
}) {
  const [name, setName] = useState(client.name)
  const [email, setEmail] = useState(client.email ?? '')
  const [notes, setNotes] = useState(client.notes)
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
      await api.updateClient(client.id, {
        name: name.trim(),
        email: email.trim() || null,
        notes,
      })
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save changes.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-4 space-y-3">
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Email">
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Notes">
        <TextArea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Goals, focus areas, context…"
        />
      </Field>
      <ErrorNote message={error} />
      <div className="flex gap-2">
        <Button onClick={() => void submit()} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function NewSessionForm({ clientId, onCreated }: { clientId: number; onCreated: () => void }) {
  const [date, setDate] = useState(todayISO())
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!date) {
      setError('Date is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.createSession(clientId, { session_date: date, title: title.trim() })
      setTitle('')
      onCreated()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create session.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Date">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <div className="min-w-48 flex-1">
          <Field label="Title (optional)">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Kickoff"
            />
          </Field>
        </div>
        <Button onClick={() => void submit()} disabled={saving}>
          {saving ? 'Adding…' : 'Add session'}
        </Button>
      </div>
      <ErrorNote message={error} />
    </div>
  )
}

function SessionRow({ session, onChanged }: { session: Session; onChanged: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-line py-3 last:border-b-0">
      <div>
        <span className="font-heading text-sm font-bold text-ink">
          {formatDate(session.session_date)}
        </span>
        {session.title && <span className="ml-3 text-sm text-ink/80">{session.title}</span>}
      </div>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-parchment px-3 py-1 font-heading text-xs font-bold uppercase tracking-wide text-heading">
          {session.status}
        </span>
        <ConfirmButton
          label="Delete"
          className="!px-2 !py-1 text-xs"
          onConfirm={() => {
            void api.deleteSession(session.id).then(onChanged)
          }}
        />
      </div>
    </div>
  )
}

export default function ClientDetailPage() {
  const { id } = useParams()
  const clientId = Number(id)
  const navigate = useNavigate()

  const [client, setClient] = useState<ClientDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [addingSession, setAddingSession] = useState(false)

  const load = useCallback(async () => {
    try {
      setClient(await api.getClient(clientId))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load client.')
    }
  }, [clientId])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return (
      <div>
        <Link to="/clients" className="font-heading text-sm font-bold text-accent">
          ← Back to clients
        </Link>
        <ErrorNote message={error} />
      </div>
    )
  }
  if (!client) return <p>Loading…</p>

  return (
    <div className="max-w-3xl">
      <Link to="/clients" className="font-heading text-sm font-bold text-accent">
        ← Back to clients
      </Link>

      <div className="mt-4 flex items-start justify-between">
        <div>
          <h2 className="text-3xl">{client.name}</h2>
          <p className="mt-1 text-sm text-ink/70">
            {client.email ?? 'No email'} · client since {formatDate(client.created_at)}
          </p>
        </div>
        {!editing && (
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}
      </div>

      <Card className="mt-6">
        {editing ? (
          <EditClientForm
            client={client}
            onSaved={() => {
              setEditing(false)
              void load()
            }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <h3 className="text-lg">Notes</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm">
              {client.notes || <span className="text-ink/50">No notes yet.</span>}
            </p>
          </>
        )}
      </Card>

      <Card className="mt-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg">
            Sessions{' '}
            <span className="font-body text-sm font-normal text-ink/50">
              ({client.session_count})
            </span>
          </h3>
          <Button
            variant={addingSession ? 'ghost' : 'primary'}
            onClick={() => setAddingSession((v) => !v)}
          >
            {addingSession ? 'Cancel' : '+ New session'}
          </Button>
        </div>

        {addingSession && (
          <NewSessionForm
            clientId={client.id}
            onCreated={() => {
              setAddingSession(false)
              void load()
            }}
          />
        )}

        <div className="mt-2">
          {client.sessions.length === 0 && !addingSession && (
            <p className="mt-3 text-sm text-ink/60">No sessions yet.</p>
          )}
          {client.sessions.map((session) => (
            <SessionRow key={session.id} session={session} onChanged={() => void load()} />
          ))}
        </div>
      </Card>

      <div className="mt-8">
        <ConfirmButton
          label="Delete client"
          onConfirm={() => {
            void api.deleteClient(client.id).then(() => navigate('/clients'))
          }}
        />
        <p className="mt-2 text-xs text-ink/50">
          Deletes the client and all of their sessions.
        </p>
      </div>
    </div>
  )
}
