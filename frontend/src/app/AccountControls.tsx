import {
  ActionIcon,
  Avatar,
  Badge,
  Button,
  Group,
  Menu,
  Popover,
  Skeleton,
  Text,
  Tooltip,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { IconInfoCircle, IconLogout, IconMoon, IconSun } from '@tabler/icons-react'
import { type Role, useSession } from '../auth/session'

const ROLE_LABELS: Record<Role, string> = {
  attendee: 'Attendee',
  organiser: 'Organiser',
  venue_staff: 'Venue staff',
}

function useColorSchemeSwitch() {
  const { setColorScheme } = useMantineColorScheme()
  const scheme = useComputedColorScheme('light')
  const next = scheme === 'dark' ? 'light' : 'dark'
  return { scheme, next, toggle: () => setColorScheme(next) }
}

function ColorSchemeToggle() {
  const { scheme, next, toggle } = useColorSchemeSwitch()
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <ActionIcon variant="default" size="lg" aria-label={`Switch to ${next} mode`} onClick={toggle}>
        {scheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  )
}

/** Shown before sign-in: what happens to an email address if you create an account. */
function PrivacyNote() {
  return (
    <Popover width={280} position="bottom-end" withArrow shadow="md">
      <Popover.Target>
        <ActionIcon variant="subtle" color="gray" size="lg" aria-label="About accounts and privacy">
          <IconInfoCircle size={18} />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown>
        <Text size="sm" fw={600} mb={4}>
          Accounts and privacy
        </Text>
        <Text size="sm" c="dimmed">
          Tessera is a demo project. New accounts (via "Sign up" on the sign-in page) are attendee
          accounts. We store your email only to sign you in; it never appears in logs or analytics.
        </Text>
      </Popover.Dropdown>
    </Popover>
  )
}

function UserMenu() {
  const session = useSession()
  const { scheme, next, toggle } = useColorSchemeSwitch()
  const email = session.user?.email ?? ''

  return (
    <Menu position="bottom-end" width={240} withinPortal>
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Avatar size={30} radius="xl" color="aegean">
            {email.slice(0, 2).toUpperCase()}
          </Avatar>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Signed in as</Menu.Label>
        <Text size="sm" px="sm" truncate="end" title={email}>
          {email}
        </Text>
        <Group gap={4} px="sm" py={6}>
          {session.user?.roles.map((role) => (
            <Badge key={role} size="sm" variant="light">
              {ROLE_LABELS[role]}
            </Badge>
          ))}
        </Group>
        <Menu.Divider />
        <Menu.Item
          leftSection={scheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
          onClick={toggle}
        >
          {next === 'dark' ? 'Dark mode' : 'Light mode'}
        </Menu.Item>
        <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={session.signOut}>
          Sign out
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}

/** Right side of the header: sign-in entry point, or the signed-in user's menu. */
export function AccountControls() {
  const session = useSession()

  if (session.status === 'loading') {
    return <Skeleton height={30} width={96} radius="sm" aria-label="Loading account" />
  }
  if (session.status === 'signedIn') return <UserMenu />
  return (
    <Group gap={4} wrap="nowrap">
      <ColorSchemeToggle />
      <PrivacyNote />
      <Button size="xs" onClick={() => session.signIn()}>
        Sign in
      </Button>
    </Group>
  )
}
