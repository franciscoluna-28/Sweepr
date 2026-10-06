<script lang="ts">
  import type { JobLimits } from './api'

  let {
    files,
    limits,
    onadd,
    onremove,
    disabled = false,
  }: {
    files: File[]
    limits: JobLimits | null
    onadd: (added: File[]) => void
    onremove: (index: number) => void
    disabled?: boolean
  } = $props()

  let over = $state(false)
  let problems = $state<string[]>([])
  let input: HTMLInputElement

  const FALLBACK_EXTS = ['wav', 'mp3', 'flac', 'ogg', 'opus']

  function mb(bytes: number): string {
    return bytes >= 1024 * 1024
      ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.max(1, Math.round(bytes / 1024))} KB`
  }

  function pick(list: FileList | null | undefined) {
    if (!list?.length) return
    const allowed = (limits?.allowed_exts ?? FALLBACK_EXTS).map((e) => '.' + e)
    const maxFiles = limits?.max_files ?? 10
    const maxMb = limits?.max_file_mb ?? 100
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
    problems = bad.slice(0, 3)
    if (ok.length) onadd(ok)
  }

  function openPicker() {
    if (!disabled) input.click()
  }
</script>

<div
  class="rounded-md p-8 text-center transition-colors {over ? 'bg-surface-3' : 'bg-surface-2'} {disabled
    ? 'opacity-60'
    : ''}"
  role="button"
  tabindex="0"
  onclick={openPicker}
  onkeydown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openPicker()
    }
  }}
  ondragover={(e) => {
    e.preventDefault()
    if (!disabled) over = true
  }}
  ondragleave={() => (over = false)}
  ondrop={(e) => {
    e.preventDefault()
    over = false
    if (!disabled) pick(e.dataTransfer?.files)
  }}
>
  <input
    type="file"
    multiple
    accept={FALLBACK_EXTS.map((e) => '.' + e).join(',')}
    class="hidden"
    bind:this={input}
    onchange={(e) => {
      pick(e.currentTarget.files)
      e.currentTarget.value = ''
    }}
  />
  <p class="m-0 text-body">
    <strong class="font-medium text-ink">Drop audio files</strong>
    <span class="text-ink-tertiary"> or </span>
    <button
      type="button"
      class="cursor-pointer border-none bg-transparent p-0 text-primary underline underline-offset-2 hover:text-primary-hover"
      onclick={(e) => {
        e.stopPropagation()
        openPicker()
      }}
    >
      browse
    </button>
  </p>
  <p class="m-0 mt-1 text-caption text-ink-tertiary">
    {limits
      ? `Up to ${limits.max_files} files · ${limits.max_file_mb} MB each · ${limits.allowed_exts.join(', ')}`
      : 'WAV, MP3, FLAC, OGG, OPUS'}
  </p>

  {#if problems.length}
    <p class="m-0 mt-3 text-caption text-red-400">
      {problems.join(' · ')}
    </p>
  {/if}

  {#if files.length}
    <ul class="mx-auto mt-4 mb-0 w-full max-w-lg list-none space-y-1 p-0 text-left">
      {#each files as f, i}
        <li class="flex items-center justify-between gap-3 rounded-sm bg-surface-1 px-2 py-1.5">
          <span class="min-w-0 truncate text-body-sm text-ink-muted">{f.name}</span>
          <span class="flex shrink-0 items-center gap-2">
            <span class="font-mono text-caption text-ink-tertiary tabular-nums">{mb(f.size)}</span>
            <button
              type="button"
              class="cursor-pointer border-none bg-transparent p-0 text-caption text-ink-tertiary hover:text-ink"
              aria-label="Remove {f.name}"
              onclick={(e) => {
                e.stopPropagation()
                onremove(i)
              }}
            >
              ✕
            </button>
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</div>
