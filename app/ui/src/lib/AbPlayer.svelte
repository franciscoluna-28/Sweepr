<script lang="ts">
  let {
    origUrl,
    enhUrl,
    filename,
  }: { origUrl: string; enhUrl: string; filename: string } = $props()
</script>

<div class="grid gap-4 sm:grid-cols-2">
  <div>
    <h3 class="m-0 mb-2 text-body-sm font-medium text-ink-subtle">Original</h3>
    <audio class="w-full" controls src={origUrl}></audio>
  </div>
  <div>
    <h3 class="m-0 mb-2 text-body-sm font-medium text-ink-subtle">Enhanced</h3>
    <audio class="w-full" controls src={enhUrl}></audio>
  </div>
</div>
<a class="btn btn-primary mt-5 h-10 w-full" href={enhUrl} download={filename}>
  Download enhanced WAV
</a>
