import { Group, Text } from '@mantine/core'

/** The Tessera mark: four mosaic tiles, one of them the amber "gold tile". */
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <Group gap={8} wrap="nowrap">
      <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
        <rect x="2" y="2" width="11" height="11" rx="2.5" fill="var(--mantine-primary-color-filled)" />
        <rect x="15" y="2" width="11" height="11" rx="2.5" fill="var(--mantine-color-amber-4)" />
        <rect x="2" y="15" width="11" height="11" rx="2.5" fill="var(--mantine-color-aegean-6)" opacity="0.7" />
        <rect x="15" y="15" width="11" height="11" rx="2.5" fill="var(--mantine-primary-color-filled)" />
      </svg>
      <Text fw={600} fz="lg">
        Tessera
      </Text>
    </Group>
  )
}
