import { Box, Paper, ScrollArea } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import type { ReactNode } from 'react'

interface SplitViewProps {
  /** Left pane: the list (with its filters). */
  list: ReactNode
  /** Right pane: details or a form for the selected item, or null when nothing is selected. */
  detail: ReactNode | null
  /** Shown in the right pane when nothing is selected: should be useful, never just blank. */
  placeholder: ReactNode
  /** Width of the list pane on wide screens. */
  listWidth?: number | string
}

/**
 * List + detail layout: the selected item fills the right pane instead of a new page, so the
 * screen is always in use and the list keeps its place. Each pane scrolls on its own.
 * On narrow screens only one pane shows: the detail when something is selected, else the list.
 */
export function SplitView({ list, detail, placeholder, listWidth = 420 }: SplitViewProps) {
  const wide = useMediaQuery('(min-width: 62em)', true)

  if (!wide) {
    return <Box>{detail ?? list}</Box>
  }

  return (
    <Box
      style={{
        display: 'grid',
        gridTemplateColumns: `${typeof listWidth === 'number' ? `${listWidth}px` : listWidth} 1fr`,
        gap: 'var(--mantine-spacing-lg)',
        height: 'calc(100dvh - var(--app-shell-header-height, 48px) - 2 * var(--mantine-spacing-lg))',
      }}
    >
      <ScrollArea type="auto" offsetScrollbars>
        {list}
      </ScrollArea>
      <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
        <ScrollArea h="100%" type="auto">
          <Box p="xl">{detail ?? placeholder}</Box>
        </ScrollArea>
      </Paper>
    </Box>
  )
}
