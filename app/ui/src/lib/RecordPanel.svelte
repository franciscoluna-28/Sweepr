<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import Controls from './Controls.svelte'
  import {
    getDevices,
    getSessionStatus,
    startSession,
    stopSession,
    updateSession,
    type DevicesResponse,
    type SessionStatus,
  } from './api'

  let devices = $state<DevicesResponse | null>(null)
  let status = $state<SessionStatus | null>(null)
  let inputId = $state<number | null>(null)
  let outputId = $state<number | null>(null)
  let atten = $state(50)
  let postFilter = $state(false)
  let error = $state('')
  let busy = $state(false)
  let timer: ReturnType<typeof setInterval> | undefined

  const running = $derived(status?.running ?? false)
  const inputName = $derived(devices?.inputs.find((d) => d.id === inputId)?.name)
  const outputName = $derived(devices?.outputs.find((d) => d.id === outputId)?.name)
  const meter = (rms: number) => `${Math.min(100, Math.round(rms * 600))}%`

  onMount(async () => {
    await load()
    timer = setInterval(refresh, 500)
  })
  onDestroy(() => clearInterval(timer))

  async function load() {
    try {
      devices = await getDevices()
      inputId =
        devices.inputs.find((d) => d.default && d.hostapi.includes('WASAPI'))?.id ??
        devices.inputs.find((d) => d.default)?.id ??
        devices.inputs[0]?.id ??
        null
      outputId =
        devices.virtual_cable ??
        devices.outputs.find((d) => d.default && d.hostapi.includes('WASAPI'))?.id ??
        devices.outputs.find((d) => d.default)?.id ??
        devices.outputs[0]?.id ??
        null
      status = await getSessionStatus()
    } catch (e) {
      error = (e as Error).message
    }
  }

  async function refresh() {
    try {
      status = await getSessionStatus()
    } catch {
      /* ignore transient errors */
    }
  }

  async function toggle() {
    if (inputId == null || outputId == null) {
      error = 'Pick an input and an output device.'
      return
    }
    busy = true
    error = ''
    try {
      status = running
        ? await stopSession()
        : await startSession({
            input_id: inputId,
            output_id: outputId,
            input_name: inputName,
            output_name: outputName,
            atten_lim_db: atten,
            post_filter: postFilter,
            block: 960,
          })
    } catch (e) {
      error = (e as Error).message
    } finally {
      busy = false
    }
  }

  $effect(() => {
    if (running && atten != null) updateSession({ atten_lim_db: atten }).catch(() => {})
  })
  $effect(() => {
    if (running) updateSession({ post_filter: postFilter }).catch(() => {})
  })
  $effect(() => {
    if (running)
      updateSession({
        input_id: inputId ?? undefined,
        output_id: outputId ?? undefined,
        input_name: inputName,
        output_name: outputName,
      }).catch(() => {})
  })
</script>

{#if devices && !devices.available}
  <section class="panel p-4 sm:p-5">
    <h2 class="m-0 text-card-title">Record mode needs the native app</h2>
    <p class="m-0 mt-2 text-body-sm text-ink-subtle">
      {devices.reason ?? 'Audio devices are unavailable here.'}
    </p>
    <p class="m-0 mt-3 text-body-sm text-ink-tertiary">
      Start the host bridge with <code class="font-mono text-ink">python audio_bridge.py</code>,
      or run the whole app natively with <code class="font-mono text-ink">run.bat</code>.
    </p>
  </section>
{:else}
<section class="panel p-4 sm:p-5">
  <div class="grid gap-4 sm:grid-cols-2">
    <label class="grid gap-1 text-body-sm text-ink-subtle">
      Microphone
      <select bind:value={inputId} class="field">
        {#each devices?.inputs ?? [] as d (d.id)}
          <option value={d.id}>{d.name} · {d.hostapi}</option>
        {/each}
      </select>
    </label>
    <label class="grid gap-1 text-body-sm text-ink-subtle">
      Virtual cable output
      <select bind:value={outputId} class="field">
        {#each devices?.outputs ?? [] as d (d.id)}
          <option value={d.id}>{d.name} · {d.hostapi}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if devices && devices.virtual_cable == null}
    <div class="mt-4 rounded-md bg-surface-2 p-3 text-body-sm text-ink-subtle">
      No virtual cable detected. Install <span class="text-ink">VB-CABLE</span> (or VoiceMeeter),
      then select “CABLE Input” as the output above and set other apps’ microphone to “CABLE
      Output”.
    </div>
  {/if}

  <div class="mt-6">
    <Controls bind:atten bind:postFilter disabled={busy} />
  </div>

  <button
    class="btn btn-primary mt-6 h-10 w-full"
    disabled={busy || inputId == null || outputId == null}
    onclick={toggle}
  >
    {running ? 'Stop virtual mic' : 'Start virtual mic'}
  </button>

  {#if running}
    <div class="mt-5 grid gap-3">
      <div class="flex items-center gap-3">
        <span class="w-16 text-body-sm text-ink-tertiary">Input</span>
        <div class="h-1.5 flex-1 overflow-hidden rounded-pill bg-surface-3">
          <div class="h-full rounded-pill bg-primary" style="width: {meter(status?.input_rms ?? 0)}">
          </div>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="w-16 text-body-sm text-ink-tertiary">Output</span>
        <div class="h-1.5 flex-1 overflow-hidden rounded-pill bg-surface-3">
          <div
            class="h-full rounded-pill bg-primary"
            style="width: {meter(status?.output_rms ?? 0)}"
          >
          </div>
        </div>
      </div>
      <p class="m-0 text-caption text-ink-tertiary">
        {status?.latency_ms ?? 0} ms buffer · {status?.drop ?? 0} dropped
      </p>
    </div>
  {/if}

  {#if error}
    <p class="m-0 mt-3 text-body-sm text-ink-subtle">{error}</p>
  {/if}
</section>
{/if}
