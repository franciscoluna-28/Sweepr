<script lang="ts">
  let {
    atten = $bindable(30),
    postFilter = $bindable(false),
    normalize = $bindable(false),
    targetLufs = $bindable(-14),
    targets = [-14, -16],
    disabled = false,
  }: {
    atten?: number
    postFilter?: boolean
    normalize?: boolean
    targetLufs?: number
    targets?: number[]
    disabled?: boolean
  } = $props()

  function targetLabel(t: number): string {
    return t <= -15 ? 'Quieter' : 'Standard'
  }
</script>

<div>
  <div class="flex items-center justify-between gap-4">
    <label for="atten" class="text-body font-medium text-ink">Noise reduction</label>
    <output for="atten" class="text-body-sm text-ink-subtle tabular-nums">{atten}%</output>
  </div>
  <input
    id="atten"
    type="range"
    min="0"
    max="100"
    step="1"
    bind:value={atten}
    {disabled}
    class="mt-4 w-full cursor-pointer accent-primary disabled:opacity-50"
  />
  <div class="mt-2 flex justify-between text-caption text-ink-tertiary">
    <span>Off</span><span>Light</span><span>Balanced</span><span>Strong</span>
  </div>
</div>

<details class="mt-6">
  <summary class="cursor-pointer select-none text-body-sm text-ink-subtle">Advanced options</summary>

  <label class="mt-4 flex items-start gap-3 text-body-sm text-ink-subtle">
    <input
      type="checkbox"
      bind:checked={postFilter}
      {disabled}
      class="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary disabled:opacity-50"
    />
    <span>Extra post-filter - over-attenuate very noisy parts</span>
  </label>

  <label class="mt-4 flex items-start gap-3 text-body-sm text-ink-subtle">
    <input
      type="checkbox"
      bind:checked={normalize}
      {disabled}
      class="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary disabled:opacity-50"
    />
    <span>Even out the volume across files</span>
  </label>
  {#if normalize}
    <div class="mt-2 flex items-center gap-3 pl-7 text-body-sm text-ink-subtle">
      <label for="target-lufs" class="text-ink-tertiary">Volume</label>
      <select
        id="target-lufs"
        bind:value={targetLufs}
        {disabled}
        class="cursor-pointer rounded-sm border border-hairline bg-surface-2 px-2 py-1 text-body-sm text-ink disabled:opacity-50"
      >
        {#each targets as t}
          <option value={t}>{targetLabel(t)} ({t} LUFS)</option>
        {/each}
      </select>
    </div>
  {/if}
</details>
