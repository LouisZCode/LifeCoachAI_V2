// Typed client for the FastAPI backend (proxied via /api in dev).

export type Session = {
  id: number
  client_id: number
  title: string
  session_date: string
  notes: string
  status: string
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`)
  }
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
  updateSession: (
    id: number,
    data: Partial<{ session_date: string; title: string; notes: string }>,
  ) => request<Session>(`/api/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSession: (id: number) =>
    request<void>(`/api/sessions/${id}`, { method: 'DELETE' }),
}

export function formatDate(iso: string): string {
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(
    undefined,
    { year: 'numeric', month: 'short', day: 'numeric' },
  )
}
