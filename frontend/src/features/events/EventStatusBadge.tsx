import { Badge } from '@mantine/core'
import type { Event } from '../../api/catalogue'

const COLOURS: Record<Event['status'], string> = {
  DRAFT: 'gray',
  PUBLISHED: 'green',
  CANCELLED: 'red',
}

export function EventStatusBadge({ status }: { status: Event['status'] }) {
  return (
    <Badge color={COLOURS[status]} ff="monospace" fw={600}>
      {status}
    </Badge>
  )
}
