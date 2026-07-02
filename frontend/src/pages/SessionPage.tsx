import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from '../api'
import type { Client, Session } from '../api'
import { Button, Card, ErrorNote, StatusChip } from '../components/ui'

const ACCEPT = '.m4a,.mp3,.wav,.mp4,.aac,.flac,.ogg,.webm'

function UploadCard({ session, onStarted }: { session: Session; onStarted: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadAudio(session.id, file)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
      setUploading(false)
    }
  }

  return (
    <Card className="mt-6">
      <h3 className="text-lg">Session audio</h3>
      <div
        className={`mt-4 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? 'border-accent bg-accent/5' : 'border-line'
        }`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const dropped = e.dataTransfer.files[0]
          if (dropped) setFile(dropped)
        }}
      >
        {file ? (
          <p className="font-heading text-sm font-bold text-ink">{file.name}</p>
        ) : (
          <p className="text-sm text-ink/60">
            Drag the session recording here (m4a, mp3, wav …)
          </p>
        )}
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="ghost" onClick={() => inputRef.current?.click()}>
            Choose file
          </Button>
          {file && (
            <Button onClick={() => void upload()} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Upload & transcribe'}
            </Button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>
      <ErrorNote message={error} />
    </Card>
  )
}

const STAGES: Record<string, string> = {
  uploaded: 'Audio saved',
  transcribing: 'Transcribing with Deepgram',
  storing: 'Saving transcript',
}

function ProgressCard({ sessionId, onFinished }: { sessionId: number; onFinished: () => void }) {
  const [stage, setStage] = useState<{ stage: string; detail: string }>({
    stage: 'uploaded',
    detail: '',
  })

  useEffect(() => {
    const source = new EventSource(`/api/sessions/${sessionId}/events`)
    source.onmessage = (event) => {
      const state = JSON.parse(event.data) as { stage: string; detail: string }
      setStage(state)
      if (state.stage === 'done' || state.stage === 'error') {
        source.close()
        onFinished()
      }
    }
    source.onerror = () => {
      source.close()
      onFinished()
    }
    return () => source.close()
  }, [sessionId, onFinished])

  const steps = Object.keys(STAGES)
  const current = steps.indexOf(stage.stage)

  return (
    <Card className="mt-6">
      <h3 className="text-lg">Transcribing…</h3>
      <div className="mt-4 space-y-3">
        {steps.map((step, i) => {
          const state = i < current ? 'done' : i === current ? 'active' : 'pending'
          return (
            <div key={step} className="flex items-center gap-3">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  state === 'done'
                    ? 'bg-heading'
                    : state === 'active'
                      ? 'animate-pulse bg-accent'
                      : 'bg-line'
                }`}
              />
              <span className={`text-sm ${state === 'pending' ? 'text-ink/40' : 'text-ink'}`}>
                {STAGES[step]}
              </span>
            </div>
          )
        })}
      </div>
      {stage.detail && <p className="mt-4 text-xs text-ink/50">{stage.detail}</p>}
    </Card>
  )
}

type Turn = { speaker: string; time: string; text: string }

function parseTranscript(md: string): { meta: string[]; turns: Turn[] } {
  const [head, ...rest] = md.split('\n---\n')
  const body = rest.join('\n---\n')
  const meta = head
    .split('\n')
    .map((l) => l.replaceAll('**', '').trim())
    .filter(Boolean)

  const turns: Turn[] = []
  for (const block of body.split(/\n(?=### )/)) {
    const match = block.match(/^### (.+?) · \[(.+?)\]\n([\s\S]*)/)
    if (match) turns.push({ speaker: match[1], time: match[2], text: match[3].trim() })
  }
  return { meta, turns }
}

const SPEAKER_COLORS = ['text-heading', 'text-accent', 'text-ink']

function TranscriptCard({ sessionId }: { sessionId: number }) {
  const [transcript, setTranscript] = useState<ReturnType<typeof parseTranscript> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getTranscript(sessionId)
      .then((text) => setTranscript(parseTranscript(text)))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load transcript.'))
  }, [sessionId])

  if (error) return <ErrorNote message={error} />
  if (!transcript) return <p className="mt-6 text-sm">Loading transcript…</p>

  const speakerColor = new Map<string, string>()
  for (const turn of transcript.turns) {
    if (!speakerColor.has(turn.speaker)) {
      speakerColor.set(turn.speaker, SPEAKER_COLORS[speakerColor.size % SPEAKER_COLORS.length])
    }
  }

  return (
    <Card className="mt-6">
      <h3 className="text-lg">Transcript</h3>
      <div className="mt-6 space-y-5">
        {transcript.turns.map((turn, i) => (
          <div key={i}>
            <p className="font-heading text-sm font-bold">
              <span className={speakerColor.get(turn.speaker)}>{turn.speaker}</span>
              <span className="ml-2 font-normal text-ink/40">{turn.time}</span>
            </p>
            <p className="mt-1 text-sm leading-relaxed">{turn.text}</p>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default function SessionPage() {
  const { id } = useParams()
  const sessionId = Number(id)

  const [session, setSession] = useState<Session | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [replacing, setReplacing] = useState(false)

  const load = useCallback(async () => {
    try {
      const s = await api.getSession(sessionId)
      setSession(s)
      setReplacing(false)
      setClient(await api.getClient(s.client_id))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load session.')
    }
  }, [sessionId])

  useEffect(() => {
    void load()
  }, [load])

  const retry = async () => {
    try {
      await api.retryTranscription(sessionId)
      void load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not restart transcription.')
    }
  }

  if (error && !session) {
    return (
      <div>
        <Link to="/clients" className="font-heading text-sm font-bold text-accent">
          ← Back to clients
        </Link>
        <ErrorNote message={error} />
      </div>
    )
  }
  if (!session) return <p>Loading…</p>

  return (
    <div className="max-w-3xl">
      <Link
        to={`/clients/${session.client_id}`}
        className="font-heading text-sm font-bold text-accent"
      >
        ← {client ? client.name : 'Back to client'}
      </Link>

      <div className="mt-4 flex items-start justify-between">
        <div>
          <h2 className="text-3xl">{session.title || 'Session'}</h2>
          <p className="mt-1 text-sm text-ink/70">
            {formatDate(session.session_date)}
            {session.duration_seconds != null &&
              ` · ${formatDuration(session.duration_seconds)}`}
            {session.audio_filename && ` · ${session.audio_filename}`}
          </p>
        </div>
        <StatusChip status={session.status} />
      </div>

      <ErrorNote message={error} />

      {(session.status === 'new' || replacing) && (
        <UploadCard session={session} onStarted={() => void load()} />
      )}

      {session.status === 'transcribing' && (
        <ProgressCard sessionId={session.id} onFinished={() => void load()} />
      )}

      {session.status === 'error' && !replacing && (
        <Card className="mt-6">
          <h3 className="text-lg">Transcription failed</h3>
          <p className="mt-2 text-sm text-accent">{session.error_message}</p>
          <div className="mt-4 flex gap-2">
            <Button onClick={() => void retry()}>Try again</Button>
            <Button variant="ghost" onClick={() => setReplacing(true)}>
              Upload different audio
            </Button>
          </div>
        </Card>
      )}

      {session.status === 'transcribed' && (
        <>
          <TranscriptCard sessionId={session.id} />
          {!replacing && (
            <div className="mt-6">
              <Button variant="ghost" onClick={() => setReplacing(true)}>
                Replace audio & re-transcribe
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
