// Hand-written fetch wrappers for the routes in app/api.py.
// No code generation, no generated client — just typed helpers.

export interface JobLimits {
  max_files: number
  max_file_mb: number
  max_total_mb: number
  max_duration_min: number
  allowed_exts: string[]
}

export interface Health {
  status: string
  models_loaded: (boolean | number)[]
  limits?: JobLimits
}

export interface JobSettings {
  atten_lim_db: number
  post_filter: boolean
}

export type FileStatus = 'queued' | 'processing' | 'done' | 'error'

export type JobStatus =
  | 'queued'
  | 'running'
  | 'done'
  | 'done_with_errors'
  | 'interrupted'

export interface JobFile {
  name: string
  stored: string
  status: FileStatus
  error: string | null
}

export interface Job {
  id: string
  created: string
  status: JobStatus
  settings: JobSettings
  files: JobFile[]
}

export interface JobParams {
  attenLimDb: number
  postFilter: boolean
}

export function isActive(status: JobStatus): boolean {
  return status === 'queued' || status === 'running'
}

async function errorFrom(res: Response): Promise<Error> {
  const body = await res.json().catch(() => null)
  const detail: unknown = body?.detail
  if (detail && typeof detail === 'object' && 'errors' in detail) {
    const errors = (detail as { errors?: unknown }).errors
    if (Array.isArray(errors) && errors.length) return new Error(errors.join(' · '))
  }
  if (typeof detail === 'string') return new Error(detail)
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return new Error(String((detail as { message: unknown }).message))
  }
  return new Error(`Request failed (${res.status})`)
}

export async function getHealth(): Promise<Health> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function listJobs(): Promise<Job[]> {
  const res = await fetch('/api/jobs')
  if (!res.ok) throw await errorFrom(res)
  return res.json()
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`/api/jobs/${id}`)
  if (!res.ok) throw await errorFrom(res)
  return res.json()
}

export async function createJob(files: File[], params: JobParams): Promise<string> {
  const form = new FormData()
  for (const f of files) form.append('files', f, f.name)
  form.append('atten_lim_db', String(params.attenLimDb))
  form.append('post_filter', String(params.postFilter))
  const res = await fetch('/api/jobs', { method: 'POST', body: form })
  if (!res.ok) throw await errorFrom(res)
  const data = await res.json()
  return data.job_id as string
}

export async function deleteJob(id: string): Promise<void> {
  const res = await fetch(`/api/jobs/${id}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) throw await errorFrom(res)
}

export function jobFileUrl(id: string, index: number, which: 'in' | 'out'): string {
  return `/api/jobs/${id}/files/${index}?which=${which}`
}

export function jobZipUrl(id: string): string {
  return `/api/jobs/${id}/zip`
}

/** Poll a job every 700 ms until it leaves an active state. Returns a stop fn. */
export function pollJob(
  id: string,
  onTick: (job: Job) => void,
  onError?: (e: Error) => void,
): () => void {
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined
  const tick = async () => {
    if (stopped) return
    try {
      const job = await getJob(id)
      if (stopped) return
      onTick(job)
      if (isActive(job.status)) timer = setTimeout(tick, 700)
    } catch (e) {
      if (!stopped) onError?.(e as Error)
    }
  }
  void tick()
  return () => {
    stopped = true
    clearTimeout(timer)
  }
}
