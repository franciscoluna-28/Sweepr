<script lang="ts">
  import { onMount } from 'svelte'
  import Controls from './lib/Controls.svelte'
  import DropZone from './lib/DropZone.svelte'
  import JobPanel from './lib/JobPanel.svelte'
  import Logo from './lib/Logo.svelte'
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

  let files = $state<File[]>([])
  let atten = $state(25)
  let postFilter = $state(false)
  let job = $state<Job | null>(null)
  let starting = $state(false)
  let error = $state('')
  let online = $state<boolean | null>(null)
  let limits = $state<JobLimits | null>(null)

  let stopPoll: (() => void) | null = null

  function watch(id: string) {
    stopPoll?.()
    stopPoll = pollJob(id, (j) => (job = j), (e) => (error = e.message))
  }

  async function start() {
    if (!files.length || starting) return
    starting = true
    error = ''
    try {
      const id = await createJob(files, { attenLimDb: atten, postFilter })
      files = []
      job = await getJob(id)
      watch(id)
    } catch (e) {
      error = (e as Error).message
    } finally {
      starting = false
    }
  }

  async function clear() {
    if (!job) return
    const id = job.id
    stopPoll?.()
    stopPoll = null
    error = ''
    try {
      await deleteJob(id)
      job = null
    } catch (e) {
      error = (e as Error).message
      watch(id)
    }
  }

  onMount(() => {
    let alive = true
    ;(async () => {
      try {
        const h = await getHealth()
        if (!alive) return
        online = h.status === 'ok'
        limits = h.limits ?? null
      } catch {
        if (alive) online = false
      }
      try {
        const jobs = await listJobs()
        if (alive && jobs.length) {
          job = jobs[0]
          if (isActive(job.status)) watch(job.id)
        }
      } catch {
        /* no previous jobs to restore */
      }
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {})
      }
    })()
    return () => {
      alive = false
      stopPoll?.()
    }
  })
</script>

<main class="container-content py-10 sm:py-14">
  <header class="mb-6">
    <h1 class="m-0"><Logo /></h1>
    <p class="m-0 mt-1 text-body-sm text-ink-subtle">
      Clean noisy audio locally. Your files never leave this machine.{#if online === false}
        <span class="text-ink-tertiary"> Backend offline.</span>{/if}
    </p>
  </header>

  <div class="grid gap-3">
    <section class="panel p-4 sm:p-5">
      <DropZone
        {files}
        {limits}
        disabled={starting}
        onadd={(added) => (files = [...files, ...added])}
        onremove={(i) => (files = files.filter((_, j) => j !== i))}
      />
    </section>

    <section class="panel p-4 sm:p-5">
      <Controls bind:atten bind:postFilter />
      <button
        class="btn btn-primary mt-6 h-10 w-full"
        disabled={!files.length || starting}
        onclick={start}
      >
        {starting ? 'Uploading…' : job && isActive(job.status) ? 'Add to queue' : 'Enhance audio'}
      </button>
      {#if error}
        <p class="m-0 mt-3 text-body-sm text-red-400">{error}</p>
      {/if}
    </section>

    {#if job}
      <JobPanel {job} onclear={clear} />
    {/if}
  </div>
</main>
