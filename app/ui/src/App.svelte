<script lang="ts">
  import { onMount } from 'svelte'
  import AbPlayer from './lib/AbPlayer.svelte'
  import DropZone from './lib/DropZone.svelte'
  import { enhance, getHealth } from './lib/api'

  let file = $state<File | null>(null)
  let atten = $state(100)
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

<main class="mx-auto max-w-2xl px-5 pb-16 pt-8">
  <header class="mb-6">
    <h1 class="m-0 text-2xl font-bold">DeepFilterNet Denoiser</h1>
    <p class="m-0 text-slate-400">
      Clean up noisy recordings. {#if online === false}<span class="text-amber-400"
          >Backend offline</span
        >{:else if online}Runs locally — audio never leaves your machine.{/if}
    </p>
  </header>

  <section class="mb-4 rounded-xl border border-line bg-ink-900 p-5">
    <DropZone {file} onpick={pick} />
  </section>

  <section class="mb-4 rounded-xl border border-line bg-ink-900 p-5">
    <label class="flex items-center justify-between gap-3">
      <span>Noise reduction strength</span>
      <output class="tabular-nums text-slate-400">{atten} dB</output>
    </label>
    <input
      type="range"
      min="0"
      max="100"
      step="1"
      bind:value={atten}
      class="my-3 w-full accent-accent"
    />
    <div class="flex justify-between text-xs text-slate-500">
      <span>Off</span><span>Light</span><span>Meeting</span><span>Max</span>
    </div>

    <label class="mt-4 flex items-start gap-3 text-sm text-slate-400">
      <input type="checkbox" bind:checked={postFilter} class="mt-0.5 accent-accent" />
      <span>Extra post-filter (over-attenuate very noisy parts)</span>
    </label>

    <button
      class="mt-5 rounded-lg bg-accent px-5 py-3 font-semibold text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-45"
      disabled={!file || loading}
      onclick={run}
    >
      {loading ? 'Processing…' : 'Enhance'}
    </button>
    {#if status}
      <p class="mb-0 mt-3 text-sm text-slate-400">{status}</p>
    {/if}
  </section>

  {#if origUrl && enhUrl}
    <section class="mb-4 rounded-xl border border-line bg-ink-900 p-5">
      <AbPlayer {origUrl} {enhUrl} filename={downloadName} />
    </section>
  {/if}
</main>
