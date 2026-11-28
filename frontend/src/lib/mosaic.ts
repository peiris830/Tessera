/** Pattern logic for generated mosaic covers (see components/MosaicCover.tsx). */

/** FNV-1a: a tiny, stable string hash. */
function hash(text: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** mulberry32: a small seeded random number generator (same seed, same sequence). */
function seededRandom(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Each event gets one of these blue "moods"; amber appears as the occasional gold tile.
const MOODS = [
  [2, 3, 4, 5],
  [4, 5, 6, 7],
  [6, 7, 8, 9],
  [1, 3, 5, 7],
  [3, 5, 7, 9],
] as const

export interface Tile {
  x: number
  y: number
  fill: string
}

export function mosaicTiles(seed: string, cols: number, rows: number): Tile[] {
  const random = seededRandom(hash(seed))
  const mood = MOODS[Math.floor(random() * MOODS.length)] ?? MOODS[0]
  const tiles: Tile[] = []
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const r = random()
      const fill =
        r < 0.07
          ? 'var(--mantine-color-amber-4)'
          : `var(--mantine-color-aegean-${mood[Math.floor(random() * mood.length)] ?? 5})`
      tiles.push({ x, y, fill })
    }
  }
  return tiles
}
