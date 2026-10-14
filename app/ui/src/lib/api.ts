// Typed client generated from the FastAPI schema.
//
// Types come from ./api-schema.d.ts (regenerate with `pnpm gen:api`). Transport
// is the tiny `openapi-fetch` wrapper; the domain helpers below (polling, direct
// file/zip URLs) stay hand-written because a generated client returns bodies,
// not URLs, and the DOM wants `src`/`href` strings.

import createClient from 'openapi-fetch'
import type { components, paths } from './api-schema'

export type Health = components['schemas']['Health']
export type JobLimits = components['schemas']['Limits']
export type JobSettings = components['schemas']['JobSettings']
export type JobFile = components['schemas']['JobFile']
export type Job = components['schemas']['Job']
export type JobStatus = Job['status']
export type FileStatus = JobFile['status']
export type ErrorDetail = components['schemas']['ErrorDetail']
export type ErrorEnvelope = components['schemas']['ErrorEnvelope']

export interface JobParams {
  attenLimDb: number
  postFilter: boolean
  normalize: boolean
  targetLufs: number
}

const client = createClient<paths>({ baseUrl: '' })

export function isActive(status: JobStatus): boolean {
  return status === 'queued' || status === 'running'
}

function errorFrom(error: ErrorEnvelope | undefined, status: number): Error {
  const detail = error?.detail
  if (detail?.errors?.length) return new Error(detail.errors.join(' · '))
  if (detail?.message) return new Error(detail.message)
  return new Error(`Request failed (${status})`)
}

export async function getHealth(): Promise<Health> {
  const { data, response } = await client.GET('/api/health')
  if (data === undefined) throw errorFrom(undefined, response.status)
  return data
}

export async function listJobs(): Promise<Job[]> {
  const { data, error, response } = await client.GET('/api/jobs')
  if (data === undefined) throw errorFrom(error, response.status)
  return data
}

export async function getJob(id: string): Promise<Job> {
  const { data, error, response } = await client.GET('/api/jobs/{job_id}', {
    params: { path: { job_id: id } },
  })
  if (data === undefined) throw errorFrom(error, response.status)
  return data
}

export async function createJob(files: File[], params: JobParams): Promise<string> {
  const { data, error, response } = await client.POST('/api/jobs', {
    // Browsers send binary as a string in the schema; the real File[] rides in
    // the serializer below (the documented openapi-fetch multipart pattern).
    body: {
      files: files as unknown as string[],
      atten_lim_db: params.attenLimDb,
      post_filter: params.postFilter,
      normalize: params.normalize,
      target_lufs: params.targetLufs,
    },
    bodySerializer(body) {
      const form = new FormData()
      for (const f of files) form.append('files', f, f.name)
      form.append('atten_lim_db', String(body.atten_lim_db))
      form.append('post_filter', String(body.post_filter))
      form.append('normalize', String(body.normalize))
      form.append('target_lufs', String(body.target_lufs))
      return form
    },
  })
  if (data === undefined) throw errorFrom(error, response.status)
  return data.job_id
}

export async function deleteJob(id: string): Promise<void> {
  const { error, response } = await client.DELETE('/api/jobs/{job_id}', {
    params: { path: { job_id: id } },
  })
  if (error && response.status !== 404) throw errorFrom(error, response.status)
}

export function jobFileUrl(id: string, index: number, which: 'in' | 'out' | 'video'): string {
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
