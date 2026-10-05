<script lang="ts">
  import { onMount } from 'svelte'
  import AbPlayer from './lib/AbPlayer.svelte'
  import DropZone from './lib/DropZone.svelte'
  import { enhance, getHealth } from './lib/api'

  let file = $state<File | null>(null)
  let atten = $state(50)
  let postFilter = $state(false)
  let loading = $state(false)
  let status = $state('')
  let origUrl = $state<string | null>(null)
  let enhUrl = $state<string | null>(null)
  let online = $state<boolean | null>(null)

  const downloadName = $derived(
    file ? file.name.replace(/\.[^.]+$/, '') + '_enhanced.wav' : 'enhanced.wav',
  )

  onMount(async () => {
    try {
      online = (await getHealth()).status === 'ok'
    } catch {
      online = false
    }
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {})
    }
  })

  function resetUrls() {
    if (origUrl) URL.revokeObjectURL(origUrl)
    if (enhUrl) URL.revokeObjectURL(enhUrl)
    origUrl = null
    enhUrl = null
  }

  function pick(f: File) {
    resetUrls()
    status = ''
    file = f
  }

  async function run() {
    if (!file) return
    loading = true
    status = 'Processing…'
    try {
      const blob = await enhance(file, { attenLimDb: atten, postFilter })
      resetUrls()
      origUrl = URL.createObjectURL(file)
      enhUrl = URL.createObjectURL(blob)
      status = 'Done'
    } catch (e) {
      status = 'Error: ' + (e as Error).message
    } finally {
      loading = false
    }
  }
</script>

<main class="container-content py-10 sm:py-14">
  <header class="mb-6">
    <h1 class="m-0 text-headline">Meowless</h1>
    <p class="m-0 mt-1 text-body-sm text-ink-subtle">
      Clean noisy recordings locally.{#if online === false}
        <span class="text-ink-tertiary">Backend offline.</span>{/if}
    </p>
  </header>

  <div class="grid gap-3">
    <section class="panel p-4 sm:p-5">
      <DropZone {file} onpick={pick} />
    </section>

    <section class="panel p-4 sm:p-5">
      <div class="flex items-center justify-between gap-4">
        <label for="atten" class="text-body font-medium">Noise reduction strength</label>
        <output for="atten" class="font-mono text-body-sm text-ink-subtle tabular-nums">
          {atten} dB
        </output>
      </div>
      <input
        id="atten"
        type="range"
        min="0"
        max="100"
        step="1"
        bind:value={atten}
        class="mt-4 w-full cursor-pointer accent-primary"
      />
      <div class="mt-2 flex justify-between text-caption text-ink-tertiary">
        <span>Off</span><span>Light</span><span>Meeting</span><span>Max</span>
      </div>

      <label class="mt-6 flex items-start gap-3 text-body-sm text-ink-subtle">
        <input
          type="checkbox"
          bind:checked={postFilter}
          class="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary"
        />
        <span>Extra post-filter - Suppress very noisy parts</span>
      </label>

      <button class="btn btn-primary mt-6 h-10 w-full" disabled={!file || loading} onclick={run}>
        {loading ? 'Processing…' : 'Enhance audio'}
      </button>
      {#if status}
        <p class="m-0 mt-3 text-body-sm text-ink-subtle">{status}</p>
      {/if}
    </section>

    {#if origUrl && enhUrl}
      <section class="panel p-4 sm:p-5">
        <AbPlayer {origUrl} {enhUrl} filename={downloadName} />
      </section>
    {/if}
  </div>
</main>
