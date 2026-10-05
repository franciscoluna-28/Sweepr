<script lang="ts">
  let { file, onpick }: { file: File | null; onpick: (f: File) => void } = $props()
  let over = $state(false)
  let input: HTMLInputElement

  function take(f?: File | null) {
    if (f) onpick(f)
  }
</script>

<div
  class="rounded-xl border-2 border-dashed p-7 text-center transition-colors {over
    ? 'border-accent bg-ink-800'
    : 'border-line'}"
  role="button"
  tabindex="0"
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
  <p class="m-0">
    <strong>Drop an audio file</strong> or
    <button class="cursor-pointer border-none bg-transparent p-0 text-[inherit] text-accent underline" onclick={() => input.click()}>
      browse
    </button>
  </p>
  <p class="mb-0 mt-1 text-sm text-slate-400">{file ? file.name : 'No file selected'}</p>
</div>
