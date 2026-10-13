<script lang="ts">
  let { size = 36 }: { size?: number } = $props()
</script>

<span class="inline-flex items-center gap-2.5">
  <svg
    viewBox="0 0 512 512"
    aria-hidden="true"
    class="shrink-0"
    style="width: {size}px; height: {size}px"
  >
    <rect width="512" height="512" rx="96" fill="#5e6ad2" />
    <g stroke="#fff" stroke-width="24" stroke-linecap="round">
      <line x1="120" y1="210" x2="120" y2="302" />
      <line x1="180" y1="170" x2="180" y2="342" />
      <line x1="240" y1="130" x2="240" y2="382" />
      <line x1="300" y1="180" x2="300" y2="332" />
      <line x1="360" y1="150" x2="360" y2="362" />
      <line x1="420" y1="215" x2="420" y2="297" />
    </g>
  </svg>
  <span class="text-headline font-semibold text-ink">Sweepr</span>
</span>
