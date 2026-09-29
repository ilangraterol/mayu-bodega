/**
 * Product thumbnail.
 *
 * Images are served as WebP thumbnails by the backend. Two details matter for
 * low-end phones:
 *   - the wrapper has a fixed `aspect-square` so the grid never shifts
 *   - `loading="lazy"` + `decoding="async"` keep off-screen products out of
 *     memory until they scroll close
 * Products without a photo fall back to a placeholder with their initials.
 */

import { useState } from 'react'

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}

interface ProductImageProps {
  src: string
  alt: string
  className?: string
}

/**
 * The backend already returns a WebP thumbnail on `primary_image_url`, so no
 * extra sizing is needed here; `srcset` is unnecessary at catalogue scale.
 */
export function ProductImage({ src, alt, className = '' }: ProductImageProps) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return (
      <div
        className={`flex aspect-square w-full items-center justify-center bg-slate-100 text-slate-400 ${className}`}
        role="img"
        aria-label={alt}
      >
        <span className="text-xl font-semibold">{initials(alt)}</span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={`aspect-square w-full bg-slate-100 object-cover ${className}`}
    />
  )
}
