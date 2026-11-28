import { render, screen } from '@testing-library/react'
import { mosaicTiles } from '../lib/mosaic'
import { MosaicCover } from './MosaicCover'

test('the same event always gets the same pattern', () => {
  expect(mosaicTiles('event-123', 8, 3)).toEqual(mosaicTiles('event-123', 8, 3))
})

test('different events get different patterns', () => {
  expect(mosaicTiles('event-123', 8, 3)).not.toEqual(mosaicTiles('event-124', 8, 3))
})

test('fills the whole grid with theme colours', () => {
  const tiles = mosaicTiles('event-123', 4, 2)
  expect(tiles).toHaveLength(8)
  expect(tiles.every((t) => t.fill.startsWith('var(--mantine-color-'))).toBe(true)
})

test('is decorative and can be greyed out', () => {
  render(<MosaicCover seed="x" muted />)
  const svg = screen.getByTestId('mosaic-cover')
  expect(svg).toHaveAttribute('aria-hidden', 'true')
  expect(svg.style.filter).toContain('grayscale')
})
