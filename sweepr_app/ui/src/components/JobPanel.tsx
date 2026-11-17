import { useState } from 'react'
import { Check, Circle, Download, LoaderCircle, X } from 'lucide-react'
import { AbCompare } from './AbCompare'
import { isActive, jobFileUrl, jobZipUrl, type Job } from '../lib/api'

type JobPanelProps = { job: Job; onClear: () => void }

function statusLabel(job: Job, doneCount: number, errorCount: number, total: number, settled: number): string {
  switch (job.status) {
    case 'queued':
      return 'Waiting in queue…'
    case 'running':
      return `Processing ${Math.min(settled + 1, total)} of ${total}…`
    case 'done':
      return `Finished - ${doneCount} file${doneCount === 1 ? '' : 's'} ready`
    case 'done_with_errors':
      return `Finished - ${doneCount} ok, ${errorCount} failed`
    case 'interrupted':
      return 'Interrupted - Sweepr closed mid-job'
    default:
      return job.status
  }
}

export function JobPanel({ job, onClear }: JobPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null)

  const total = job.files.length
  const doneCount = job.files.filter((f) => f.status === 'done').length
  const errorCount = job.files.filter((f) => f.status === 'error').length
  const settled = doneCount + errorCount
  const pct = total ? Math.round((settled / total) * 100) : 0
  const active = isActive(job.status)
  const label = statusLabel(job, doneCount, errorCount, total, settled)

  let eta: string | null = null
  if (active && settled > 0) {
    const elapsed = (Date.now() - Date.parse(job.created)) / 1000
    const remaining = Math.round((elapsed / settled) * (total - settled))
    if (isFinite(remaining) && remaining >= 1) {
      const m = Math.floor(remaining / 60)
      const s = remaining % 60
      eta = m > 0 ? `~${m}m ${s}s left` : `~${s}s left`
    }
  }

  return (
    <section className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="m-0 text-body font-medium text-ink">{label}</p>
          {eta && <p className="m-0 mt-0.5 text-caption text-ink-tertiary">{eta}</p>}
        </div>
        <div className="flex items-center gap-2">
          {doneCount > 0 && (
            <a
              className="btn h-8 border border-hairline bg-surface-2 px-3 text-body-sm text-ink hover:bg-surface-3"
              href={jobZipUrl(job.id)}
              download
            >
              Download .zip
            </a>
          )}
          <button
            type="button"
            className="btn h-8 border border-hairline bg-surface-2 px-3 text-body-sm text-ink-subtle hover:bg-surface-3"
            onClick={onClear}
          >
            {active ? 'Stop' : 'Start over'}
          </button>
        </div>
      </div>

      <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </div>

      <ul className="m-4 list-none space-y-1 p-0">
        {job.files.map((f, i) => (
          <li key={`${f.name}-${i}`} className="rounded-md bg-surface-2 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-2 text-body-sm text-ink-muted">
                {f.status === 'done' ? (
                  <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
                ) : f.status === 'error' ? (
                  <X className="size-4 shrink-0 text-red-400" aria-hidden="true" />
                ) : f.status === 'processing' ? (
                  <LoaderCircle className="size-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
                ) : (
                  <Circle className="size-4 shrink-0 text-ink-tertiary" aria-hidden="true" />
                )}
                <span className="truncate">{f.name}</span>
              </span>
              <span className="flex shrink-0 items-center gap-3">
                {f.status === 'done' ? (
                  <>
                    <button
                      type="button"
                      className={`inline-flex cursor-pointer items-center rounded-sm border-none bg-transparent p-1 transition-colors hover:text-ink ${
                        expanded === i ? 'text-primary' : 'text-ink-tertiary'
                      }`}
                      title={expanded === i ? 'Hide before/after comparison' : 'Compare original and enhanced'}
                      aria-label={expanded === i ? 'Hide before/after comparison' : 'Compare original and enhanced'}
                      aria-expanded={expanded === i}
                      onClick={() => setExpanded(expanded === i ? null : i)}
                    >
                      <AbCompare size={18} />
                    </button>
                    <a
                      className="btn btn-primary h-7 gap-1.5 px-2.5 text-body-sm"
                      href={jobFileUrl(job.id, i, f.video ? 'video' : 'out')}
                      download
                      title={f.video ? 'Download video with enhanced audio' : 'Download enhanced audio'}
                    >
                      <Download className="size-4" aria-hidden="true" />
                      Download
                    </a>
                  </>
                ) : f.status === 'processing' ? (
                  <span className="text-caption text-primary">working…</span>
                ) : f.status === 'error' ? (
                  <span className="text-caption text-red-400">failed</span>
                ) : (
                  <span className="text-caption text-ink-tertiary">queued</span>
                )}
              </span>
            </div>
            {f.status === 'error' && f.error && <p className="m-0 mt-1 text-caption text-red-400">{f.error}</p>}
            {expanded === i && f.status === 'done' && (
              <div className="mt-3 grid gap-3 pt-3 sm:grid-cols-2">
                <div>
                  <p className="m-0 mb-1 text-caption text-ink-tertiary">Original</p>
                  <audio className="w-full" controls preload="none" src={jobFileUrl(job.id, i, 'in')} />
                </div>
                <div>
                  <p className="m-0 mb-1 text-caption text-ink-tertiary">Enhanced</p>
                  <audio className="w-full" controls preload="none" src={jobFileUrl(job.id, i, 'out')} />
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
