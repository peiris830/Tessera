import { useMemo } from 'react'
import { mosaicTiles } from '../lib/mosaic'

/**
 * Generated cover art: a mosaic of tiles derived from a seed (the event ID), so every event has
 * its own recognisable pattern without storing any image. Colours are theme CSS variables, so
 * covers follow light/dark mode. Purely decorative (hidden from screen readers).
 */

interface MosaicCoverProps {
  seed: string
  cols?: number
  rows?: number
  /** CSS width/height of the cover; the SVG stretches to fill it. */
  width?: number | string
  height?: number | string
  radius?: number | string
  /** Greyed out, e.g. for cancelled events. */
  muted?: boolean
}

export function MosaicCover({
  seed,
  cols = 8,
  rows = 3,
  width = '100%',
  height = 96,
  radius = 'var(--mantine-radius-md)',
  muted = false,
}: MosaicCoverProps) {
  const tiles = useMemo(() => mosaicTiles(seed, cols, rows), [seed, cols, rows])
  const gap = 0.08 // grout between tiles, in tile units

  return (
    <svg
      aria-hidden="true"
      data-testid="mosaic-cover"
      viewBox={`0 0 ${cols} ${rows}`}
      preserveAspectRatio="none"
      style={{
        width,
        height,
        display: 'block',
        flexShrink: 0,
        borderRadius: radius,
        background: 'var(--mantine-color-default-border)',
        filter: muted ? 'grayscale(1) opacity(0.6)' : undefined,
      }}
    >
      {tiles.map((t) => (
        <rect
          key={`${t.x}-${t.y}`}
          x={t.x + gap / 2}
          y={t.y + gap / 2}
          width={1 - gap}
          height={1 - gap}
          rx={0.12}
          fill={t.fill}
        />
      ))}
    </svg>
  )
}
