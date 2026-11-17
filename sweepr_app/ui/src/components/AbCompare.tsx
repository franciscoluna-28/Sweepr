import type { SVGProps } from 'react'

/** A/B icon: two labelled tracks with a divider. */
export function AbCompare({ size = 24, ...rest }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <path d="M10.5 19.5 13.5 4.5" />
      <text x="5" y="16.5" fontSize={10} fontWeight={600} textAnchor="middle" fill="currentColor" stroke="none">
        A
      </text>
      <text x="19" y="16.5" fontSize={10} fontWeight={600} textAnchor="middle" fill="currentColor" stroke="none">
        B
      </text>
    </svg>
  )
}
