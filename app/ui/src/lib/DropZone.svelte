<script lang="ts">
  let { file, onpick }: { file: File | null; onpick: (f: File) => void } = $props()
  let over = $state(false)
  let input: HTMLInputElement

  function take(f?: File | null) {
    if (f) onpick(f)
  }
</script>

<div
  class="rounded-md p-8 text-center transition-colors {over ? 'bg-surface-3' : 'bg-surface-2'}"
  role="button"
  tabindex="0"
  onclick={() => input.click()}
  onkeydown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      input.click()
    }
  }}
  ondragover={(e) => {
    e.preventDefault()
    over = true
  }}
  ondragleave={() => (over = false)}
  ondrop={(e) => {
    e.preventDefault()
    over = false
    take(e.dataTransfer?.files?.[0])
  }}
>
  <input
    type="file"
    accept="audio/*"
    class="hidden"
    bind:this={input}
    onchange={(e) => take(e.currentTarget.files?.[0])}
  />
  <p class="m-0 text-body">
    <strong class="font-medium text-ink">Drop an audio file</strong>
    <span class="text-ink-tertiary"> or </span>
    <button
      type="button"
      class="cursor-pointer border-none bg-transparent p-0 text-primary underline underline-offset-2 hover:text-primary-hover"
      onclick={(e) => {
        e.stopPropagation()
        input.click()
      }}
    >
      browse
    </button>
  </p>
  <p class="m-0 mt-1 text-body-sm {file ? 'text-ink-muted' : 'text-ink-tertiary'}">
    {file ? file.name : 'No file selected'}
  </p>
</div>
