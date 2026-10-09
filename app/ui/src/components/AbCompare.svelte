<script lang="ts">
  import type { LucideProps } from '@lucide/svelte'

  let { size = 24, ...rest }: LucideProps = $props()
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  {...rest}
>
  <path d="M10.5 19.5 13.5 4.5" />
  <text
    x="5"
    y="16.5"
    font-size="10"
    font-weight="600"
    text-anchor="middle"
    fill="currentColor"
    stroke="none">A</text
  >
  <text
    x="19"
    y="16.5"
    font-size="10"
    font-weight="600"
    text-anchor="middle"
    fill="currentColor"
    stroke="none">B</text
  >
</svg>
