<script lang="ts">
  import logoUrl from '../assets/logo.png'

  let { size = 36 }: { size?: number } = $props()
</script>

<span class="inline-flex items-center gap-2.5">
  <img
    src={logoUrl}
    alt=""
    aria-hidden="true"
    class="shrink-0"
    style="width: {size}px; height: {size}px"
  />
  <span class="text-headline font-semibold text-ink">Meowless</span>
</span>
