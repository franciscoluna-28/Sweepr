import { useEffect, useRef, useState } from 'react'
import { Controls } from './components/Controls'
import { DropZone } from './components/DropZone'
import { JobPanel } from './components/JobPanel'
import { Logo } from './components/Logo'
import {
  createJob,
  deleteJob,
  getHealth,
  getJob,
  isActive,
  listJobs,
  pollJob,
  type Job,
  type JobLimits,
} from './lib/api'

export default function App() {
  const [files, setFiles] = useState<File[]>([])
  const [atten, setAtten] = useState(30)
  const [postFilter, setPostFilter] = useState(false)
  const [normalize, setNormalize] = useState(false)
  const [targetLufs, setTargetLufs] = useState(-14)
  const [job, setJob] = useState<Job | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const [online, setOnline] = useState<boolean | null>(null)
  const [limits, setLimits] = useState<JobLimits | null>(null)
  const stopPoll = useRef<(() => void) | null>(null)

  const watch = (id: string) => {
    stopPoll.current?.()
    stopPoll.current = pollJob(id, setJob, (e) => setError(e.message))
  }

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const h = await getHealth()
        if (!alive) return
        setOnline(h.status === 'ok')
        setLimits(h.limits ?? null)
      } catch {
        if (alive) setOnline(false)
      }
      try {
        const jobs = await listJobs()
        if (alive && jobs.length) {
          setJob(jobs[0])
          if (isActive(jobs[0].status)) watch(jobs[0].id)
        }
      } catch {
        /* no previous jobs to restore */
      }
    })()
    return () => {
      alive = false
      stopPoll.current?.()
    }
    // Mount-only: watch() only touches refs and state setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function start() {
    if (!files.length || starting) return
    setStarting(true)
    setError('')
    try {
      const id = await createJob(files, { attenLimDb: atten, postFilter, normalize, targetLufs })
      setFiles([])
      setJob(await getJob(id))
      watch(id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  async function clear() {
    if (!job) return
    const id = job.id
    stopPoll.current?.()
    stopPoll.current = null
    setError('')
    try {
      await deleteJob(id)
      setJob(null)
    } catch (e) {
      setError((e as Error).message)
      watch(id)
    }
  }

  return (
    <main className="container-content py-10 sm:py-14">
      <header className="mb-6">
        <h1 className="m-0">
          <Logo />
        </h1>
        <p className="m-0 mt-1 text-body-sm text-ink-subtle">
          Clean noisy audio locally. Your files never leave this machine.
          {online === false && <span className="text-ink-tertiary"> Backend offline.</span>}
        </p>
      </header>

      <div className="grid gap-3">
        <section className="panel p-4 sm:p-5">
          <DropZone
            files={files}
            limits={limits}
            disabled={starting}
            onAdd={(added) => setFiles((prev) => [...prev, ...added])}
            onRemove={(i) => setFiles((prev) => prev.filter((_, j) => j !== i))}
          />
        </section>

        <section className="panel p-4 sm:p-5">
          <Controls
            atten={atten}
            onAtten={setAtten}
            postFilter={postFilter}
            onPostFilter={setPostFilter}
            normalize={normalize}
            onNormalize={setNormalize}
            targetLufs={targetLufs}
            onTargetLufs={setTargetLufs}
            targets={limits?.normalize_targets ?? [-14, -16]}
          />
          <button
            type="button"
            className="btn btn-primary mt-6 h-10 w-full"
            disabled={!files.length || starting}
            onClick={start}
          >
            {starting ? 'Uploading…' : 'Clean my audio'}
          </button>
          {error && <p className="m-0 mt-3 text-body-sm text-red-400">{error}</p>}
        </section>

        {job && <JobPanel job={job} onClear={clear} />}
      </div>
    </main>
  )
}
