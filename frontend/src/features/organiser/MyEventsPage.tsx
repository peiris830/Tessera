import {
  ActionIcon,
  Badge,
  Button,
  Group,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  ThemeIcon,
  Title,
  Tooltip,
} from '@mantine/core'
import { IconEdit, IconPlus, IconSearch, IconSend, IconSparkles } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import type { Event } from '../../api/catalogue'
import { MosaicCover } from '../../components/MosaicCover'
import { SplitView } from '../../components/SplitView'
import { formatEventDateShort } from '../../lib/datetime'
import { EventDetail } from '../events/EventDetail'
import { EventStatusBadge } from '../events/EventStatusBadge'
import { SAMPLE_EVENTS } from '../events/fixtures'
import { EventForm } from './EventForm'
import classes from './MyEventsPage.module.css'

type StatusFilter = 'ALL' | Event['status']
const BASE = '/organiser/events'

/** Organiser console: own events (table with filters) + edit/create form in the detail pane. */
export function MyEventsPage() {
  const { eventId } = useParams()
  const creating = useLocation().pathname === `${BASE}/new`
  const navigate = useNavigate()
  const [status, setStatus] = useState<StatusFilter>('ALL')
  const [query, setQuery] = useState('')

  const events = SAMPLE_EVENTS // 5d: the caller's own events from /v1/organisers/me/events
  const counts = useMemo(() => {
    const c = { ALL: events.length, DRAFT: 0, PUBLISHED: 0, CANCELLED: 0 }
    for (const e of events) c[e.status] += 1
    return c
  }, [events])
  const visible = events.filter(
    (e) =>
      (status === 'ALL' || e.status === status) &&
      e.title.toLowerCase().includes(query.trim().toLowerCase()),
  )
  const selected = events.find((e) => e.eventId === eventId) ?? null
  const close = () => navigate(BASE)

  const list = (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="sm">
          <Title order={1}>My events</Title>
          <Badge variant="outline" color="amber.7">
            Sample data
          </Badge>
        </Group>
        <Button leftSection={<IconPlus size={16} />} onClick={() => navigate(`${BASE}/new`)}>
          New event
        </Button>
      </Group>

      <Group gap="sm" wrap="wrap">
        <SegmentedControl
          size="xs"
          value={status}
          onChange={(v) => setStatus(v as StatusFilter)}
          aria-label="Filter by status"
          data={[
            { label: `All ${counts.ALL}`, value: 'ALL' },
            { label: `Drafts ${counts.DRAFT}`, value: 'DRAFT' },
            { label: `Published ${counts.PUBLISHED}`, value: 'PUBLISHED' },
            { label: `Cancelled ${counts.CANCELLED}`, value: 'CANCELLED' },
          ]}
        />
        <TextInput
          size="xs"
          placeholder="Filter by title"
          leftSection={<IconSearch size={14} />}
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          aria-label="Filter by title"
          style={{ flex: 1, minWidth: 160 }}
        />
      </Group>

      <Table striped highlightOnHover verticalSpacing="sm" stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Event</Table.Th>
            <Table.Th>Starts</Table.Th>
            <Table.Th ta="right">Cap.</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th aria-label="Actions" />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {visible.map((e) => (
            <Table.Tr
              key={e.eventId}
              className={classes.row}
              data-selected={e.eventId === eventId || undefined}
              onClick={() => navigate(`${BASE}/${e.eventId}`)}
            >
              <Table.Td>
                <Group gap="sm" wrap="nowrap">
                  <MosaicCover
                    seed={e.eventId}
                    cols={3}
                    rows={3}
                    width={32}
                    height={32}
                    radius="var(--mantine-radius-sm)"
                    muted={e.status === 'CANCELLED'}
                  />
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} fz="sm" lineClamp={1}>
                      {e.title}
                    </Text>
                    <Text fz="xs" c="dimmed" lineClamp={1}>
                      {e.venue.name}, {e.venue.city}
                    </Text>
                  </div>
                </Group>
              </Table.Td>
              <Table.Td ff="monospace" fz="xs" style={{ whiteSpace: 'nowrap' }}>
                {formatEventDateShort(e.startsAt)}
              </Table.Td>
              <Table.Td ff="monospace" fz="xs" ta="right">
                {e.capacity}
              </Table.Td>
              <Table.Td>
                <EventStatusBadge status={e.status} />
              </Table.Td>
              <Table.Td>
                {/* Row actions appear on hover/focus (always shown on touch screens). */}
                <Group gap={4} wrap="nowrap" justify="flex-end" className={classes.actions}>
                  {e.status !== 'CANCELLED' && (
                    <Tooltip label="Edit">
                      <ActionIcon
                        variant="subtle"
                        aria-label={`Edit ${e.title}`}
                        onClick={(click) => {
                          click.stopPropagation()
                          navigate(`${BASE}/${e.eventId}`)
                        }}
                      >
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {e.status === 'DRAFT' && (
                    <Tooltip label="Publish">
                      <ActionIcon
                        variant="subtle"
                        aria-label={`Publish ${e.title}`}
                        onClick={(click) => {
                          click.stopPropagation()
                          navigate(`${BASE}/${e.eventId}`)
                        }}
                      >
                        <IconSend size={16} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {visible.length === 0 && (
        <Text c="dimmed" ta="center" py="lg">
          No events match this filter.
        </Text>
      )}
    </Stack>
  )

  const detail = creating ? (
    <EventForm key="new" event={null} onClose={close} />
  ) : selected?.status === 'CANCELLED' ? (
    <EventDetail event={selected} />
  ) : selected ? (
    <EventForm key={selected.eventId} event={selected} onClose={close} />
  ) : null

  const placeholder = (
    <Stack align="center" justify="center" gap="md" mih={320} ta="center">
      <ThemeIcon size={48} variant="light" radius="xl">
        <IconSparkles size={24} />
      </ThemeIcon>
      <Title order={2}>
        {counts.DRAFT} drafts · {counts.PUBLISHED} published
      </Title>
      <Text c="dimmed" fz="sm" maw={360}>
        Select an event to edit it here, or create a new one. Drafts are only visible to you
        until you publish them.
      </Text>
      <Button variant="light" leftSection={<IconPlus size={16} />} onClick={() => navigate(`${BASE}/new`)}>
        New event
      </Button>
    </Stack>
  )

  return <SplitView list={list} detail={detail} placeholder={placeholder} listWidth="minmax(520px, 55%)" />
}
