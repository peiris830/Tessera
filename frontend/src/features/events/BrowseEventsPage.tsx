import {
  Badge,
  Button,
  Group,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { IconCalendarEvent, IconChevronRight, IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { MosaicCover } from '../../components/MosaicCover'
import { SplitView } from '../../components/SplitView'
import { formatEventDateShort, formatEventDateTime } from '../../lib/datetime'
import classes from './BrowseEventsPage.module.css'
import { EventDetail } from './EventDetail'
import { SAMPLE_EVENTS } from './fixtures'

type Range = 'week' | 'month' | 'all'
const RANGE_DAYS: Record<Range, number> = { week: 7, month: 31, all: Infinity }
const upcoming = SAMPLE_EVENTS.filter((e) => e.status === 'PUBLISHED')

/** Attendee home: upcoming published events (list) + the selected event (detail pane). */
export function BrowseEventsPage() {
  const { eventId } = useParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [range, setRange] = useState<Range>('all')
  // The cut-off is computed when the filter changes (an event handler), not during render.
  const [until, setUntil] = useState(Infinity)
  const changeRange = (next: Range) => {
    setRange(next)
    setUntil(Date.now() + RANGE_DAYS[next] * 86_400_000)
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return upcoming.filter(
      (e) =>
        Date.parse(e.startsAt) <= until &&
        (!q || `${e.title} ${e.venue.name} ${e.venue.city}`.toLowerCase().includes(q)),
    )
  }, [query, until])

  const selected = SAMPLE_EVENTS.find((e) => e.eventId === eventId) ?? null
  const next = upcoming[0]

  const list = (
    <Stack gap="md">
      <Group justify="space-between" align="baseline">
        <Title order={1}>Upcoming events</Title>
        <Badge variant="outline" color="amber.7">
          Sample data
        </Badge>
      </Group>
      <TextInput
        placeholder="Search by title, venue or city"
        leftSection={<IconSearch size={16} />}
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        aria-label="Search events"
      />
      <SegmentedControl
        size="xs"
        value={range}
        onChange={(v) => changeRange(v as Range)}
        data={[
          { label: 'This week', value: 'week' },
          { label: 'This month', value: 'month' },
          { label: 'All upcoming', value: 'all' },
        ]}
        aria-label="Date range"
      />

      <Stack gap={6} component="ul" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {visible.map((event) => (
          <li key={event.eventId}>
            <UnstyledButton
              className={classes.item}
              data-selected={event.eventId === eventId || undefined}
              onClick={() => navigate(`/events/${event.eventId}`)}
              aria-current={event.eventId === eventId ? 'true' : undefined}
            >
              <Group gap="md" wrap="nowrap">
                <MosaicCover seed={event.eventId} cols={4} rows={4} width={64} height={64} />
                <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                  <Text ff="monospace" fz="xs" c="aegean.6">
                    {formatEventDateShort(event.startsAt)}
                  </Text>
                  <Text fw={600} truncate>
                    {event.title}
                  </Text>
                  <Text fz="sm" c="dimmed">
                    {event.venue.name}, {event.venue.city} ·{' '}
                    <Text span ff="monospace" fz="xs">
                      {event.capacity}
                    </Text>{' '}
                    places
                  </Text>
                </Stack>
                <IconChevronRight size={16} className={classes.chevron} />
              </Group>
            </UnstyledButton>
          </li>
        ))}
      </Stack>

      {visible.length === 0 && (
        <Text c="dimmed" ta="center" py="xl">
          No events match. Try another search or date range.
        </Text>
      )}
      <Button variant="default" disabled>
        Load more
      </Button>
    </Stack>
  )

  const placeholder = (
    <Stack align="center" justify="center" gap="md" mih={320} ta="center">
      <ThemeIcon size={48} variant="light" radius="xl">
        <IconCalendarEvent size={24} />
      </ThemeIcon>
      <Title order={2}>{upcoming.length} upcoming events</Title>
      {next && (
        <Text c="dimmed">
          Next up: <b>{next.title}</b>, {formatEventDateTime(next.startsAt)}
        </Text>
      )}
      <Text c="dimmed" fz="sm">
        Select an event on the left to see its details here.
      </Text>
    </Stack>
  )

  return (
    <SplitView
      list={list}
      detail={selected && <EventDetail event={selected} />}
      placeholder={placeholder}
    />
  )
}
