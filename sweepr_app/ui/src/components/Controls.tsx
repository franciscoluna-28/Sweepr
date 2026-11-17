type ControlsProps = {
  atten: number
  onAtten: (value: number) => void
  postFilter: boolean
  onPostFilter: (value: boolean) => void
  normalize: boolean
  onNormalize: (value: boolean) => void
  targetLufs: number
  onTargetLufs: (value: number) => void
  targets?: number[]
  disabled?: boolean
}

function targetLabel(t: number): string {
  return t <= -15 ? 'Quieter' : 'Standard'
}

export function Controls({
  atten,
  onAtten,
  postFilter,
  onPostFilter,
  normalize,
  onNormalize,
  targetLufs,
  onTargetLufs,
  targets = [-14, -16],
  disabled = false,
}: ControlsProps) {
  return (
    <>
      <div>
        <div className="flex items-center justify-between gap-4">
          <label htmlFor="atten" className="text-body font-medium text-ink">
            Noise reduction
          </label>
          <output htmlFor="atten" className="text-body-sm text-ink-subtle tabular-nums">
            {atten}%
          </output>
        </div>
        <input
          id="atten"
          type="range"
          min={0}
          max={100}
          step={1}
          value={atten}
          onChange={(e) => onAtten(Number(e.currentTarget.value))}
          disabled={disabled}
          className="mt-4 w-full cursor-pointer accent-primary disabled:opacity-50"
        />
        <div className="mt-2 flex justify-between text-caption text-ink-tertiary">
          <span>Off</span>
          <span>Light</span>
          <span>Balanced</span>
          <span>Strong</span>
        </div>
      </div>

      <details className="mt-6">
        <summary className="cursor-pointer select-none text-body-sm text-ink-subtle">Advanced options</summary>

        <label className="mt-4 flex items-start gap-3 text-body-sm text-ink-subtle">
          <input
            type="checkbox"
            checked={postFilter}
            onChange={(e) => onPostFilter(e.currentTarget.checked)}
            disabled={disabled}
            className="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary disabled:opacity-50"
          />
          <span>Extra post-filter - over-attenuate very noisy parts</span>
        </label>

        <label className="mt-4 flex items-start gap-3 text-body-sm text-ink-subtle">
          <input
            type="checkbox"
            checked={normalize}
            onChange={(e) => onNormalize(e.currentTarget.checked)}
            disabled={disabled}
            className="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary disabled:opacity-50"
          />
          <span>Even out the volume across files</span>
        </label>
        {normalize && (
          <div className="mt-2 flex items-center gap-3 pl-7 text-body-sm text-ink-subtle">
            <label htmlFor="target-lufs" className="text-ink-tertiary">
              Volume
            </label>
            <select
              id="target-lufs"
              value={targetLufs}
              onChange={(e) => onTargetLufs(Number(e.currentTarget.value))}
              disabled={disabled}
              className="cursor-pointer rounded-sm border border-hairline bg-surface-2 px-2 py-1 text-body-sm text-ink disabled:opacity-50"
            >
              {targets.map((t) => (
                <option key={t} value={t}>
                  {targetLabel(t)} ({t} LUFS)
                </option>
              ))}
            </select>
          </div>
        )}
      </details>
    </>
  )
}
