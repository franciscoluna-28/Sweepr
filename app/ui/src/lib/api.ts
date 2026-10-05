// Hand-written fetch wrappers for the server in app/main.py.
// No code generation, no generated client — just typed helpers.

export interface Health {
  status: string
  models_loaded: (boolean | number)[]
}

export interface EnhanceParams {
  attenLimDb: number
  postFilter: boolean
}

export async function getHealth(): Promise<Health> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function enhance(file: File, params: EnhanceParams): Promise<Blob> {
  const form = new FormData()
  form.append('file', file)
  form.append('atten_lim_db', String(params.attenLimDb))
  form.append('post_filter', String(params.postFilter))
  const res = await fetch('/api/enhance', { method: 'POST', body: form })
  if (!res.ok) {
    const msg = await res.json().catch(() => ({}))
    throw new Error(msg.detail || res.statusText)
  }
  return res.blob()
}

export interface Device {
  id: number
  name: string
  hostapi: string
  samplerate: number
  channels: number
  default: boolean
}

export interface DevicesResponse {
  inputs: Device[]
  outputs: Device[]
  virtual_cable: number | null
  available: boolean
  reason: string | null
}

export interface SessionStatus {
  running: boolean
  error: string | null
  input_id: number | null
  output_id: number | null
  atten_lim_db: number
  post_filter: boolean
  block: number
  latency_ms: number
  input_rms: number
  output_rms: number
  drop: number
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const msg = await res.json().catch(() => ({}))
    throw new Error(msg.detail || res.statusText)
  }
  return res.json()
}

export function getDevices(): Promise<DevicesResponse> {
  return fetch('/api/devices').then((r) => json<DevicesResponse>(r))
}

export function getSessionStatus(): Promise<SessionStatus> {
  return fetch('/api/session/status').then((r) => json<SessionStatus>(r))
}

export function startSession(body: {
  input_id: number
  output_id: number
  input_name?: string
  output_name?: string
  atten_lim_db: number
  post_filter: boolean
  block: number
}): Promise<SessionStatus> {
  return fetch('/api/session/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => json<SessionStatus>(r))
}

export function stopSession(): Promise<SessionStatus> {
  return fetch('/api/session/stop', { method: 'POST' }).then((r) => json<SessionStatus>(r))
}

export function updateSession(body: {
  atten_lim_db?: number
  post_filter?: boolean
  input_id?: number
  output_id?: number
  input_name?: string
  output_name?: string
  block?: number
}): Promise<SessionStatus> {
  return fetch('/api/session', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => json<SessionStatus>(r))
}
