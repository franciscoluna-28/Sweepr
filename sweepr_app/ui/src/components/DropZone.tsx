import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import type { JobLimits } from '../lib/api'

const FALLBACK_EXTS = ['wav', 'mp3', 'flac', 'ogg', 'opus', 'mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v']

function mb(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

type DropZoneProps = {
  files: File[]
  limits: JobLimits | null
  onAdd: (added: File[]) => void
  onRemove: (index: number) => void
  disabled?: boolean
}

export function DropZone({ files, limits, onAdd, onRemove, disabled = false }: DropZoneProps) {
  const [over, setOver] = useState(false)
  const [problems, setProblems] = useState<string[]>([])
  const input = useRef<HTMLInputElement>(null)

  function pick(list: FileList | null | undefined) {
    if (!list?.length) return
    const allowed = (limits?.allowed_exts ?? FALLBACK_EXTS).map((e) => '.' + e)
    const maxFiles = limits?.max_files ?? 10
    // Before /api/health resolves we don't know the server's cap, so don't
    // invent one the server wouldn't enforce; the server stays the judge.
    const maxMb = limits?.max_file_mb ?? Number.POSITIVE_INFINITY
    const bad: string[] = []
    const ok: File[] = []
    for (const f of Array.from(list)) {
      const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase()
      if (!allowed.includes(ext)) {
        bad.push(`${f.name}: format not supported`)
        continue
      }
      if (f.size > maxMb * 1024 * 1024) {
        bad.push(`${f.name}: larger than ${maxMb} MB`)
        continue
      }
      if (files.length + ok.length >= maxFiles) {
        bad.push(`limit is ${maxFiles} files per job`)
        continue
      }
      ok.push(f)
    }
    setProblems(bad.slice(0, 3))
    if (ok.length) onAdd(ok)
  }

  function openPicker() {
    if (!disabled) input.current?.click()
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setOver(false)
    if (!disabled) pick(e.dataTransfer?.files)
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openPicker()
    }
  }

  return (
    <div
      className={`rounded-md p-8 text-center transition-colors ${over ? 'bg-surface-3' : 'bg-surface-2'} ${
        disabled ? 'opacity-60' : ''
      }`}
      role="button"
      tabIndex={0}
      onClick={openPicker}
      onKeyDown={onKey}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <input
        type="file"
        multiple
        accept={FALLBACK_EXTS.map((e) => '.' + e).join(',')}
        className="hidden"
        ref={input}
        onChange={(e) => {
          pick(e.currentTarget.files)
          e.currentTarget.value = ''
        }}
      />
      <p className="m-0 text-body">
        <strong className="font-medium text-ink">Drop audio or video files</strong>
        <span className="text-ink-tertiary"> or </span>
        <button
          type="button"
          className="cursor-pointer border-none bg-transparent p-0 text-primary underline underline-offset-2 hover:text-primary-hover"
          onClick={(e) => {
            e.stopPropagation()
            openPicker()
          }}
        >
          browse
        </button>
      </p>
      <p className="m-0 mt-1 text-caption text-ink-tertiary">
        {limits
          ? `Up to ${limits.max_files} files · ${limits.max_file_mb} MB each · ${limits.allowed_exts.join(', ')}`
          : 'WAV, MP3, FLAC, OGG, OPUS, MP4, MOV, MKV, WEBM, AVI, M4V'}
      </p>

      {problems.length > 0 && <p className="m-0 mt-3 text-caption text-red-400">{problems.join(' · ')}</p>}

      {files.length > 0 && (
        <ul className="mx-auto mt-4 mb-0 w-full max-w-lg list-none space-y-1 p-0 text-left">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-3 rounded-sm bg-surface-1 px-2 py-1.5">
              <span className="min-w-0 truncate text-body-sm text-ink-muted">{f.name}</span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-caption text-ink-tertiary tabular-nums">{mb(f.size)}</span>
                <button
                  type="button"
                  className="cursor-pointer border-none bg-transparent p-0 text-caption text-ink-tertiary hover:text-ink"
                  aria-label={`Remove ${f.name}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onRemove(i)
                  }}
                >
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
