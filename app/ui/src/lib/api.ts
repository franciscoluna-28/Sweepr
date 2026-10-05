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
