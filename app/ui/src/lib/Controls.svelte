<script lang="ts">
  let {
    atten = $bindable(25),
    postFilter = $bindable(false),
    disabled = false,
  }: { atten?: number; postFilter?: boolean; disabled?: boolean } = $props()
</script>

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
  {disabled}
  class="mt-4 w-full cursor-pointer accent-primary disabled:opacity-50"
/>
<div class="mt-2 flex justify-between text-caption text-ink-tertiary">
  <span>Off</span><span>Light</span><span>Meeting</span><span>Max</span>
</div>

<label class="mt-6 flex items-start gap-3 text-body-sm text-ink-subtle">
  <input
    type="checkbox"
    bind:checked={postFilter}
    {disabled}
    class="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary disabled:opacity-50"
  />
  <span>Extra post-filter - over-attenuate very noisy parts</span>
</label>
