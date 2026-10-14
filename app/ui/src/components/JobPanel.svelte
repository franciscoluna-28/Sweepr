<script lang="ts">
  import {
    Check,
    Circle,
    Download,
    Film,
    LoaderCircle,
    X,
  } from '@lucide/svelte'
  import AbCompare from './AbCompare.svelte'
  import { isActive, jobFileUrl, jobZipUrl, type Job } from '../lib/api'

  let { job, onclear }: { job: Job; onclear: () => void } = $props()

  let expanded = $state<number | null>(null)

  const total = $derived(job.files.length)
  const doneCount = $derived(job.files.filter((f) => f.status === 'done').length)
  const errorCount = $derived(job.files.filter((f) => f.status === 'error').length)
  const settled = $derived(doneCount + errorCount)
  const pct = $derived(total ? Math.round((settled / total) * 100) : 0)
  const active = $derived(isActive(job.status))

  const statusLabel = $derived.by(() => {
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
        return 'Interrupted - the server restarted mid-job'
      default:
        return job.status
    }
  })

  const eta = $derived.by(() => {
    if (!active || settled === 0) return null
    const elapsed = (Date.now() - Date.parse(job.created)) / 1000
    const remaining = Math.round((elapsed / settled) * (total - settled))
    if (!isFinite(remaining) || remaining < 1) return null
    const m = Math.floor(remaining / 60)
    const s = remaining % 60
    return m > 0 ? `~${m}m ${s}s left` : `~${s}s left`
  })
</script>

<section class="panel p-4 sm:p-5">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <p class="m-0 text-body font-medium text-ink">{statusLabel}</p>
      {#if eta}
        <p class="m-0 mt-0.5 text-caption text-ink-tertiary">{eta}</p>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      {#if doneCount > 0}
        <a
          class="btn h-8 border border-hairline bg-surface-2 px-3 text-body-sm text-ink hover:bg-surface-3"
          href={jobZipUrl(job.id)}
          download
        >
          Download .zip
        </a>
      {/if}
      <button
        type="button"
        class="btn h-8 border border-hairline bg-surface-2 px-3 text-body-sm text-ink-subtle hover:bg-surface-3"
        onclick={onclear}
      >
        {active ? 'Cancel' : 'Clear'}
      </button>
    </div>
  </div>

  <div class="mt-3 h-1 w-full overflow-hidden rounded-full bg-surface-3">
    <div
      class="h-full rounded-full bg-primary transition-[width] duration-300"
      style="width: {pct}%"
    ></div>
  </div>

  <ul class="m-4 list-none space-y-1 p-0">
    {#each job.files as f, i}
      <li class="rounded-md bg-surface-2 px-3 py-2">
        <div class="flex items-center justify-between gap-3">
          <span class="flex min-w-0 items-center gap-2 text-body-sm text-ink-muted">
            {#if f.status === 'done'}
              <Check class="size-4 shrink-0 text-success" aria-hidden="true" />
            {:else if f.status === 'error'}
              <X class="size-4 shrink-0 text-red-400" aria-hidden="true" />
            {:else if f.status === 'processing'}
              <LoaderCircle class="size-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
            {:else}
              <Circle class="size-4 shrink-0 text-ink-tertiary" aria-hidden="true" />
            {/if}
            <span class="truncate">{f.name}</span>
          </span>
          <span class="flex shrink-0 items-center gap-3">
            {#if f.status === 'done'}
              <button
                type="button"
                class="inline-flex cursor-pointer items-center rounded-sm border-none bg-transparent p-1 transition-colors hover:text-ink {expanded === i
                  ? 'text-primary'
                  : 'text-ink-tertiary'}"
                title={expanded === i ? 'Hide A/B comparison' : 'Compare original and enhanced'}
                aria-label={expanded === i ? 'Hide A/B comparison' : 'Compare original and enhanced'}
                aria-expanded={expanded === i}
                onclick={() => (expanded = expanded === i ? null : i)}
              >
                <AbCompare class="size-[18px]" />
              </button>
              {#if f.video}
                <a
                  class="btn btn-primary h-7 gap-1.5 px-2.5 text-body-sm"
                  href={jobFileUrl(job.id, i, 'video')}
                  download
                  title="Download video with enhanced audio"
                >
                  <Film class="size-4" aria-hidden="true" />
                  Video
                </a>
                <a
                  class="btn h-7 gap-1.5 border border-hairline bg-surface-2 px-2.5 text-body-sm text-ink-subtle hover:bg-surface-3 hover:text-ink"
                  href={jobFileUrl(job.id, i, 'out')}
                  download
                  title="Download enhanced audio (WAV)"
                >
                  <Download class="size-4" aria-hidden="true" />
                  Audio
                </a>
              {:else}
                <a
                  class="btn btn-primary h-7 gap-1.5 px-2.5 text-body-sm"
                  href={jobFileUrl(job.id, i, 'out')}
                  download
                  title="Download enhanced audio (WAV)"
                >
                  <Download class="size-4" aria-hidden="true" />
                  Audio
                </a>
              {/if}
            {:else if f.status === 'processing'}
              <span class="text-caption text-primary">working…</span>
            {:else if f.status === 'error'}
              <span class="text-caption text-red-400">failed</span>
            {:else}
              <span class="text-caption text-ink-tertiary">queued</span>
            {/if}
          </span>
        </div>
        {#if f.status === 'done' && f.lufs_after != null}
          <p class="m-0 mt-1 font-mono text-caption text-ink-tertiary tabular-nums">
            {#if f.lufs_before != null}{f.lufs_before.toFixed(1)} dB → {/if}{f.lufs_after.toFixed(
              1,
            )} LUFS
          </p>
        {/if}
        {#if f.status === 'error' && f.error}
          <p class="m-0 mt-1 text-caption text-red-400">{f.error}</p>
        {/if}
        {#if expanded === i && f.status === 'done'}
          <div class="mt-3 grid gap-3 pt-3 sm:grid-cols-2">
            <div>
              <p class="m-0 mb-1 text-caption text-ink-tertiary">Original</p>
              <audio class="w-full" controls preload="none" src={jobFileUrl(job.id, i, 'in')}></audio>
            </div>
            <div>
              <p class="m-0 mb-1 text-caption text-ink-tertiary">Enhanced</p>
              <audio class="w-full" controls preload="none" src={jobFileUrl(job.id, i, 'out')}></audio>
            </div>
          </div>
        {/if}
      </li>
    {/each}
  </ul>
</section>
