import { Badge, Button, Stack, Text, Title } from '@mantine/core'
import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <Stack align="center" gap="md" py={80} ta="center">
      <Badge color="gray" ff="monospace" size="lg">
        404
      </Badge>
      <Title order={1}>Page not found</Title>
      <Text c="dimmed" maw={420}>
        This page doesn't exist, or the link is no longer valid.
      </Text>
      <Button component={Link} to="/events" variant="default">
        Back to upcoming events
      </Button>
    </Stack>
  )
}
