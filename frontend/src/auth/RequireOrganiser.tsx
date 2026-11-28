import { Button, Center, Loader, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { IconLock, IconUserX } from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { Link, Outlet } from 'react-router'
import { hasRole, useSession } from './session'

/**
 * Guards the organiser pages. Hiding the nav link isn't protection (anyone can type the URL),
 * so direct visits get an explanation instead of a broken page. The real protection is the
 * API, which rejects non-organisers with 401/403 whatever the UI shows.
 */
export function RequireOrganiser() {
  const session = useSession()

  if (session.status === 'loading') {
    return (
      <Center mih={240}>
        <Loader size="sm" aria-label="Checking your session" />
      </Center>
    )
  }
  if (session.status === 'signedOut') {
    return (
      <Panel icon={<IconLock size={20} />} title="Sign in to manage your events">
        <Text size="sm" c="dimmed">
          The organiser console is for organiser accounts. Sign in and you'll come straight back here.
        </Text>
        <Button onClick={() => session.signIn()}>Sign in</Button>
      </Panel>
    )
  }
  if (!hasRole(session, 'organiser')) {
    return (
      <Panel icon={<IconUserX size={20} />} title="Organisers only">
        <Text size="sm" c="dimmed">
          You're signed in as {session.user?.email}, which isn't an organiser account. Organiser
          accounts are set up by the Tessera team.
        </Text>
        <Button component={Link} to="/events" variant="light">
          Browse events
        </Button>
      </Panel>
    )
  }
  return <Outlet />
}

function Panel({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <Center mih={320}>
      <Paper withBorder p="xl" radius="md" maw={440}>
        <Stack align="flex-start" gap="sm">
          <ThemeIcon variant="light" size="lg" radius="md">
            {icon}
          </ThemeIcon>
          <Title order={2} size="h4">
            {title}
          </Title>
          {children}
        </Stack>
      </Paper>
    </Center>
  )
}
