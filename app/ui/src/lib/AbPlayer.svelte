<script lang="ts">
  let {
    origUrl,
    enhUrl,
    filename,
  }: { origUrl: string; enhUrl: string; filename: string } = $props()
</script>

<div class="grid gap-4 sm:grid-cols-2">
  <div>
    <h3 class="mb-2 mt-0 text-sm font-normal text-slate-400">Original</h3>
    <audio class="w-full" controls src={origUrl}></audio>
  </div>
  <div>
    <h3 class="mb-2 mt-0 text-sm font-normal text-slate-400">Enhanced</h3>
    <audio class="w-full" controls src={enhUrl}></audio>
  </div>
</div>
<a
  class="mt-5 block rounded-lg bg-accent px-5 py-3 text-center font-semibold text-white no-underline hover:bg-accent-hover"
  href={enhUrl}
  download={filename}
>
  Download enhanced WAV
</a>
