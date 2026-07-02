import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from '../api'
import type { Client, RecordingPreflight, Session, SessionDocument } from '../api'
import { Button, Card, ConfirmButton, ErrorNote, StatusChip } from '../components/ui'
import DocEditor from '../components/DocEditor'

const ACCEPT = '.m4a,.mp3,.wav,.mp4,.aac,.flac,.ogg,.webm'

function formatElapsed(seconds: number): string {
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = s % 60
  const mmss = `${String(m).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
  return h > 0 ? `${h}:${mmss}` : mmss
}

function CheckRow({ ok, label, hint }: { ok: boolean; label: string; hint?: string }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${ok ? 'bg-heading' : 'bg-accent'}`}
      />
      <div>
        <p className={`text-sm ${ok ? 'text-ink' : 'text-accent'}`}>{label}</p>
        {!ok && hint && <p className="mt-1 text-xs text-ink/60">{hint}</p>}
      </div>
    </div>
  )
}

function RecordCard({ session, onStarted }: { session: Session; onStarted: () => void }) {
  const [preflight, setPreflight] = useState<RecordingPreflight | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const check = () =>
      api
        .recordingPreflight()
        .then((p) => alive && setPreflight(p))
        .catch(() => alive && setPreflight(null))
    void check()
    const timer = setInterval(check, 2000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const start = async () => {
    setStarting(true)
    setError(null)
    try {
      await api.startRecording(session.id)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start recording.')
      setStarting(false)
    }
  }

  const busyElsewhere =
    preflight?.active_session_id != null && preflight.active_session_id !== session.id

  return (
    <Card className="mt-6">
      <h3 className="text-lg">Record the call</h3>
      {!preflight ? (
        <p className="mt-3 text-sm text-ink/60">Checking audio devices…</p>
      ) : (
        <div className="mt-4 space-y-3">
          <CheckRow
            ok={preflight.mic.found}
            label={
              preflight.mic.found
                ? `Microphone: ${preflight.mic.name}`
                : 'No microphone found'
            }
            hint="Pick a microphone in System Settings → Sound → Input."
          />
          <CheckRow
            ok={preflight.blackhole.found}
            label={
              preflight.blackhole.found
                ? `Call audio: ${preflight.blackhole.name}`
                : 'BlackHole 2ch not installed'
            }
            hint="Install it with 'brew install blackhole-2ch', then in Audio MIDI Setup create a Multi-Output Device named 'Recording Output' that combines your headphones + BlackHole 2ch."
          />
          <CheckRow
            ok={preflight.output.ok}
            label={
              preflight.output.ok
                ? `Sound output: ${preflight.output.name}`
                : `Sound output is '${preflight.output.name ?? 'unknown'}' — switch to 'Recording Output'`
            }
            hint="System Settings → Sound → Output → 'Recording Output', before joining the call. Otherwise the client's side won't be captured."
          />
        </div>
      )}
      <div className="mt-5 flex items-center gap-3">
        <Button
          onClick={() => void start()}
          disabled={!preflight?.ready || starting || busyElsewhere}
        >
          {starting ? 'Starting…' : '● Start recording'}
        </Button>
        {busyElsewhere && (
          <span className="text-xs text-ink/60">
            A recording is already running in another session.
          </span>
        )}
      </div>
      <ErrorNote message={error} />
    </Card>
  )
}

function LevelMeter({ label, level }: { label: string; level: number }) {
  const pct = Math.min(100, Math.round(Math.sqrt(Math.max(level, 0)) * 250))
  return (
    <div>
      <p className="mb-1 font-heading text-xs font-bold uppercase tracking-wide text-ink/60">
        {label}
      </p>
      <div className="h-2 overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full bg-heading transition-[width] duration-150"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function ActiveRecordingCard({
  session,
  clientName,
  onFinished,
}: {
  session: Session
  clientName: string
  onFinished: () => void
}) {
  const [elapsed, setElapsed] = useState(0)
  const [micLevel, setMicLevel] = useState(0)
  const [systemLevel, setSystemLevel] = useState(0)
  const [output, setOutput] = useState<{ name: string | null; ok: boolean } | null>(null)
  const [stale, setStale] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const timer = setInterval(() => {
      api
        .recordingStatus()
        .then((s) => {
          if (!alive) return
          if (!s.active || s.session_id !== session.id) {
            setStale(true)
            return
          }
          setStale(false)
          setElapsed(s.elapsed_seconds ?? 0)
          setMicLevel(s.mic_level ?? 0)
          setSystemLevel(s.system_level ?? 0)
          setOutput(s.output ?? null)
        })
        .catch(() => undefined)
    }, 400)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [session.id])

  const stop = async () => {
    setStopping(true)
    setError(null)
    try {
      await api.stopRecording(session.id)
      onFinished()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not stop the recording.')
      setStopping(false)
    }
  }

  const reset = async () => {
    try {
      await api.cancelRecording(session.id)
      onFinished()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reset the session.')
    }
  }

  if (stale) {
    return (
      <Card className="mt-6">
        <h3 className="text-lg">Recording interrupted</h3>
        <p className="mt-2 text-sm text-ink/70">
          The recording is no longer running (the backend may have restarted). No audio
          was saved — reset the session to start over.
        </p>
        <div className="mt-4">
          <Button onClick={() => void reset()}>Reset session</Button>
        </div>
        <ErrorNote message={error} />
      </Card>
    )
  }

  return (
    <Card className="mt-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg">Recording…</h3>
        <span className="font-heading text-2xl font-bold tabular-nums text-accent">
          {formatElapsed(elapsed)}
        </span>
      </div>
      <div className="mt-5 space-y-4">
        <LevelMeter label="Maria (microphone)" level={micLevel} />
        <LevelMeter label={`${clientName} (call audio)`} level={systemLevel} />
      </div>
      {output &&
        (output.ok ? (
          <p className="mt-4 flex items-center gap-2 text-xs text-heading">
            <span className="h-2 w-2 rounded-full bg-heading" />
            Sound output: {output.name} — all ok
          </p>
        ) : (
          <p className="mt-4 flex items-start gap-2 text-sm font-bold text-accent">
            <span className="mt-1 h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-accent" />
            Sound output switched to '{output.name ?? 'unknown'}' — the client's voice
            is NOT being recorded! Set it back to 'Recording Output' in System
            Settings → Sound.
          </p>
        ))}
      <p className="mt-3 text-xs text-ink/50">
        Both bars should move while each side is speaking.
      </p>
      <div className="mt-5 flex items-center gap-2">
        <Button onClick={() => void stop()} disabled={stopping}>
          {stopping ? 'Saving…' : '■ Stop & transcribe'}
        </Button>
        <ConfirmButton label="Discard" onConfirm={() => void reset()} />
      </div>
      <ErrorNote message={error} />
    </Card>
  )
}

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
      <h3 className="text-lg">Or upload an existing recording</h3>
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

const TRANSCRIPTION_STAGES: Record<string, string> = {
  uploaded: 'Audio ready',
  transcribing: 'Transcribing with Deepgram',
  storing: 'Saving transcript',
}

const GENERATION_STAGES: Record<string, string> = {
  analyzing: 'Analyzing the transcript',
  writing_summary: 'Writing the summary',
  writing_homework: 'Writing the homework',
  writing_next: 'Preparing the next session',
  storing: 'Saving documents',
}

function ProgressCard({
  sessionId,
  title,
  stages,
  onFinished,
}: {
  sessionId: number
  title: string
  stages: Record<string, string>
  onFinished: () => void
}) {
  const firstStage = Object.keys(stages)[0]
  const [stage, setStage] = useState<{ stage: string; detail: string }>({
    stage: firstStage,
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

  const steps = Object.keys(stages)
  const current = steps.indexOf(stage.stage)

  return (
    <Card className="mt-6">
      <h3 className="text-lg">{title}</h3>
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
                {stages[step]}
              </span>
            </div>
          )
        })}
      </div>
      {stage.detail && <p className="mt-4 text-xs text-ink/50">{stage.detail}</p>}
    </Card>
  )
}

function GenerateDocsCard({ session, onStarted }: { session: Session; onStarted: () => void }) {
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async () => {
    setStarting(true)
    setError(null)
    try {
      await api.generateDocuments(session.id)
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start generation.')
      setStarting(false)
    }
  }

  // A failed generation falls back to status "transcribed" with the reason here
  const previousFailure = session.error_message

  return (
    <Card className="mt-6">
      <h3 className="text-lg">Session documents</h3>
      <p className="mt-2 text-sm text-ink/70">
        Generate the summary, homework and next-session preparation from the
        transcript. You can edit everything afterwards.
      </p>
      {previousFailure && <ErrorNote message={previousFailure} />}
      <div className="mt-4">
        <Button onClick={() => void generate()} disabled={starting}>
          {starting ? 'Starting…' : previousFailure ? 'Try again' : '✦ Generate documents'}
        </Button>
      </div>
      <ErrorNote message={error} />
    </Card>
  )
}

const DOC_TABS: { type: SessionDocument['doc_type']; label: string }[] = [
  { type: 'summary', label: 'Summary' },
  { type: 'homework', label: 'Homework' },
  { type: 'next_session', label: 'Next Session' },
]

function DocumentsCard({ session, onRegenerate }: { session: Session; onRegenerate: () => void }) {
  const [documents, setDocuments] = useState<SessionDocument[] | null>(null)
  const [active, setActive] = useState<SessionDocument['doc_type']>('summary')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listDocuments(session.id)
      .then(setDocuments)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load documents.'))
  }, [session.id])

  const regenerate = async () => {
    try {
      await api.generateDocuments(session.id)
      onRegenerate()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not restart generation.')
    }
  }

  const current = documents?.find((d) => d.doc_type === active)

  return (
    <Card className="mt-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg">Session documents</h3>
        <ConfirmButton label="Regenerate all" onConfirm={() => void regenerate()} />
      </div>
      <p className="mt-1 text-xs text-ink/50">
        Regenerating replaces all three documents — including your edits.
      </p>
      <div className="mt-4 flex gap-2 border-b border-line">
        {DOC_TABS.map((tab) => (
          <button
            key={tab.type}
            type="button"
            onClick={() => setActive(tab.type)}
            className={`-mb-px rounded-t-lg border-x border-t px-4 py-2 font-heading text-sm font-bold transition-colors ${
              active === tab.type
                ? 'border-line bg-cream text-heading'
                : 'border-transparent text-ink/50 hover:text-ink'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-5">
        {error && <ErrorNote message={error} />}
        {!documents && !error && <p className="text-sm text-ink/60">Loading documents…</p>}
        {documents && !current && (
          <p className="text-sm text-ink/60">This document was not generated yet.</p>
        )}
        {current && <DocEditor key={current.id} document={current} />}
      </div>
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
        <>
          <RecordCard session={session} onStarted={() => void load()} />
          <UploadCard session={session} onStarted={() => void load()} />
        </>
      )}

      {session.status === 'recording' && (
        <ActiveRecordingCard
          session={session}
          clientName={client ? client.name.split(' ')[0] : 'Client'}
          onFinished={() => void load()}
        />
      )}

      {session.status === 'transcribing' && (
        <ProgressCard
          sessionId={session.id}
          title="Transcribing…"
          stages={TRANSCRIPTION_STAGES}
          onFinished={() => void load()}
        />
      )}

      {session.status === 'generating' && (
        <ProgressCard
          sessionId={session.id}
          title="Generating documents…"
          stages={GENERATION_STAGES}
          onFinished={() => void load()}
        />
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
          {!replacing && <GenerateDocsCard session={session} onStarted={() => void load()} />}
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

      {session.status === 'docs_ready' && (
        <>
          <DocumentsCard session={session} onRegenerate={() => void load()} />
          <TranscriptCard sessionId={session.id} />
        </>
      )}
    </div>
  )
}
