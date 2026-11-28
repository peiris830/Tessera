import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconLock } from '@tabler/icons-react'
import dayjs from 'dayjs'
import type { Event } from '../../api/catalogue'
import { EventStatusBadge } from '../events/EventStatusBadge'

interface FormValues {
  title: string
  description: string
  venueName: string
  city: string
  startsAt: string | null
  capacity: number | string
}

/**
 * Create / edit form in the organiser's detail pane. Validation mirrors the Catalogue API
 * (services/catalogue/src/app/models.py); the server still validates everything.
 * Saving is wired to the API in step 5d; for now it only shows a notification.
 */
export function EventForm({ event, onClose }: { event: Event | null; onClose: () => void }) {
  const isPublished = event?.status === 'PUBLISHED'
  const [confirmOpen, confirm] = useDisclosure(false)

  const form = useForm<FormValues>({
    mode: 'uncontrolled',
    initialValues: {
      title: event?.title ?? '',
      description: event?.description ?? '',
      venueName: event?.venue.name ?? '',
      city: event?.venue.city ?? '',
      startsAt: event ? dayjs(event.startsAt).format('YYYY-MM-DD HH:mm:ss') : null,
      capacity: event?.capacity ?? '',
    },
    validate: {
      title: (v) => (v.trim() ? null : 'Title is required'),
      venueName: (v) => (v.trim() ? null : 'Venue name is required'),
      city: (v) => (v.trim() ? null : 'City is required'),
      startsAt: (v) =>
        v && dayjs(v).isAfter(dayjs()) ? null : 'Start date and time must be in the future',
      capacity: (v) =>
        Number.isInteger(v) && Number(v) >= 1 && Number(v) <= 1_000_000
          ? null
          : 'Whole number between 1 and 1,000,000',
    },
  })

  const notConnected = (action: string) => {
    notifications.show({
      title: `${action} (preview)`,
      message: 'Saving to the Catalogue API is connected in step 5d.',
    })
  }

  return (
    <form onSubmit={form.onSubmit(() => notConnected(event ? 'Changes saved' : 'Draft created'))}>
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={2}>{event ? 'Edit event' : 'Create event'}</Title>
          <EventStatusBadge status={event?.status ?? 'DRAFT'} />
        </Group>

        <TextInput
          label="Title"
          placeholder="e.g. Summer Jazz Night"
          withAsterisk
          maxLength={200}
          key={form.key('title')}
          {...form.getInputProps('title')}
        />
        <Textarea
          label="Description"
          description="Optional: programme, doors-open time, accessibility notes"
          autosize
          minRows={3}
          maxRows={8}
          maxLength={5000}
          key={form.key('description')}
          {...form.getInputProps('description')}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          <TextInput
            label="Venue name"
            withAsterisk
            maxLength={200}
            key={form.key('venueName')}
            {...form.getInputProps('venueName')}
          />
          <TextInput
            label="City"
            withAsterisk
            maxLength={100}
            key={form.key('city')}
            {...form.getInputProps('city')}
          />
          <DateTimePicker
            label="Starts at (your local time)"
            withAsterisk
            valueFormat="DD MMM YYYY, HH:mm"
            key={form.key('startsAt')}
            {...form.getInputProps('startsAt')}
          />
          <NumberInput
            label="Capacity"
            withAsterisk
            min={1}
            max={1_000_000}
            allowDecimal={false}
            thousandSeparator=","
            disabled={isPublished}
            rightSection={
              isPublished ? (
                <Tooltip label="Capacity can't change after publishing: reservations rely on it">
                  <IconLock size={16} aria-label="Capacity locked" />
                </Tooltip>
              ) : undefined
            }
            key={form.key('capacity')}
            {...form.getInputProps('capacity')}
          />
        </SimpleGrid>

        {isPublished && (
          <Alert variant="light" color="aegean">
            This event is live: changes are visible to attendees immediately.
          </Alert>
        )}

        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          {event?.status === 'DRAFT' && (
            <Button variant="light" onClick={confirm.open}>
              Publish…
            </Button>
          )}
          <Button type="submit">{event ? 'Save changes' : 'Create draft'}</Button>
        </Group>
      </Stack>

      <Modal opened={confirmOpen} onClose={confirm.close} title="Publish this event?" centered>
        <Stack gap="md">
          <Text>Attendees will be able to see it and, later, reserve places.</Text>
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={confirm.close}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                confirm.close()
                notConnected('Event published')
              }}
            >
              Publish event
            </Button>
          </Group>
        </Stack>
      </Modal>
    </form>
  )
}
