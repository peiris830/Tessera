import { Alert, Button, Group, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { IconCalendar, IconMapPin, IconTicket, IconUsers } from '@tabler/icons-react'
import type { ReactNode } from 'react'
import type { Event } from '../../api/catalogue'
import { MosaicCover } from '../../components/MosaicCover'
import { formatEventDateTime } from '../../lib/datetime'
import { EventStatusBadge } from './EventStatusBadge'

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <Group gap="sm" wrap="nowrap" align="flex-start">
      <ThemeIcon variant="light" size="md">
        {icon}
      </ThemeIcon>
      <div>
        <Text fz="xs" c="dimmed" fw={600}>
          {label}
        </Text>
        <Text fz="md">{children}</Text>
      </div>
    </Group>
  )
}

/** Detail pane for one event (attendee view). */
export function EventDetail({ event }: { event: Event }) {
  return (
    <Stack gap="lg">
      <MosaicCover
        seed={event.eventId}
        cols={16}
        rows={3}
        height={120}
        muted={event.status === 'CANCELLED'}
      />
      <Stack gap="xs">
        <div>
          <EventStatusBadge status={event.status} />
        </div>
        <Title order={1}>{event.title}</Title>
      </Stack>

      {event.status === 'CANCELLED' && (
        <Alert color="red" variant="light" title="This event has been cancelled">
          It's no longer taking reservations.
        </Alert>
      )}

      <Group gap="xl" align="flex-start">
        <Fact icon={<IconCalendar size={16} />} label="Date & time">
          <Text span ff="monospace" fz="sm">
            {formatEventDateTime(event.startsAt)}
          </Text>
        </Fact>
        <Fact icon={<IconMapPin size={16} />} label="Venue">
          {event.venue.name}, {event.venue.city}
        </Fact>
        <Fact icon={<IconUsers size={16} />} label="Capacity">
          <Text span ff="monospace" fz="sm">
            {event.capacity.toLocaleString('en-GB')} places
          </Text>
        </Fact>
      </Group>

      <Stack gap="xs" maw={680}>
        <Title order={3}>About this event</Title>
        <Text c="dimmed" style={{ whiteSpace: 'pre-line' }}>
          {event.description || 'No description yet.'}
        </Text>
      </Stack>

      <Group>
        <Button leftSection={<IconTicket size={16} />} disabled>
          Reserve: coming soon
        </Button>
        <Text fz="xs" c="dimmed">
          Reservations open with the Reservation service.
        </Text>
      </Group>
    </Stack>
  )
}
