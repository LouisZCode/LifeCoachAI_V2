// Typed client for the FastAPI backend (proxied via /api in dev).

export type Session = {
  id: number
  client_id: number
  title: string
  session_date: string
  notes: string
  status: string
  audio_filename: string | null
  audio_source: string | null
  duration_seconds: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export type Client = {
  id: number
  name: string
  email: string | null
  notes: string
  session_count: number
  created_at: string
  updated_at: string
}

export type ClientDetail = Client & { sessions: Session[] }

export type Health = {
  status: string
  app: string
  version: string
  langfuse: { configured: boolean; connected: boolean }
}

export type RecordingPreflight = {
  mic: { found: boolean; name: string | null }
  blackhole: { found: boolean; name: string | null }
  output: { name: string | null; ok: boolean }
  ready: boolean
  active_session_id: number | null
}

export type RecordingStatus = {
  active: boolean
  session_id?: number
  elapsed_seconds?: number
  mic_level?: number
  system_level?: number
  output?: { name: string | null; ok: boolean }
}

async function rawRequest(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, {
    // JSON header only for string bodies — FormData sets its own boundary
    headers: typeof init?.body === 'string' ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`)
  }
  return res
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await rawRequest(path, init)
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const api = {
  health: () => request<Health>('/api/health'),

  listClients: () => request<Client[]>('/api/clients'),
  createClient: (data: { name: string; email?: string | null; notes?: string }) =>
    request<Client>('/api/clients', { method: 'POST', body: JSON.stringify(data) }),
  getClient: (id: number) => request<ClientDetail>(`/api/clients/${id}`),
  updateClient: (
    id: number,
    data: Partial<{ name: string; email: string | null; notes: string }>,
  ) => request<Client>(`/api/clients/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteClient: (id: number) =>
    request<void>(`/api/clients/${id}`, { method: 'DELETE' }),

  createSession: (
    clientId: number,
    data: { session_date: string; title?: string; notes?: string },
  ) =>
    request<Session>(`/api/clients/${clientId}/sessions`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getSession: (id: number) => request<Session>(`/api/sessions/${id}`),
  updateSession: (
    id: number,
    data: Partial<{ session_date: string; title: string; notes: string }>,
  ) => request<Session>(`/api/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSession: (id: number) =>
    request<void>(`/api/sessions/${id}`, { method: 'DELETE' }),

  uploadAudio: (sessionId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Session>(`/api/sessions/${sessionId}/audio`, { method: 'POST', body: form })
  },
  retryTranscription: (sessionId: number) =>
    request<Session>(`/api/sessions/${sessionId}/transcribe`, { method: 'POST' }),
  getTranscript: (sessionId: number) =>
    rawRequest(`/api/sessions/${sessionId}/transcript`).then((res) => res.text()),

  recordingPreflight: () => request<RecordingPreflight>('/api/recording/preflight'),
  recordingStatus: () => request<RecordingStatus>('/api/recording/status'),
  startRecording: (sessionId: number) =>
    request<Session>(`/api/sessions/${sessionId}/recording/start`, { method: 'POST' }),
  stopRecording: (sessionId: number) =>
    request<Session>(`/api/sessions/${sessionId}/recording/stop`, { method: 'POST' }),
  cancelRecording: (sessionId: number) =>
    request<Session>(`/api/sessions/${sessionId}/recording/cancel`, { method: 'POST' }),
}

export function formatDuration(seconds: number): string {
  const mins = Math.round(seconds / 60)
  if (mins < 60) return `${Math.max(mins, 1)} min`
  const h = Math.floor(mins / 60)
  return `${h} h ${String(mins % 60).padStart(2, '0')} min`
}

export function formatDate(iso: string): string {
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(
    undefined,
    { year: 'numeric', month: 'short', day: 'numeric' },
  )
}
