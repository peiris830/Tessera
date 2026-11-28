import {
  ActionIcon,
  AppShell,
  Burger,
  Button,
  Drawer,
  Group,
  Stack,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconMoon, IconSun } from '@tabler/icons-react'
import { NavLink, Outlet } from 'react-router'
import { Logo } from '../components/Logo'

// 5b: links are filtered by the signed-in user's Cognito groups (organisers also see My events).
const NAV = [
  { to: '/events', label: 'Browse events' },
  { to: '/organiser/events', label: 'My events' },
]

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return NAV.map((item) => (
    <NavLink key={item.to} to={item.to} onClick={onNavigate} style={{ textDecoration: 'none' }}>
      {({ isActive }) => (
        <Button
          component="span"
          variant={isActive ? 'light' : 'subtle'}
          color={isActive ? undefined : 'gray'}
          size="sm"
          fullWidth={Boolean(onNavigate)}
          justify={onNavigate ? 'flex-start' : undefined}
        >
          {item.label}
        </Button>
      )}
    </NavLink>
  ))
}

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme()
  const scheme = useComputedColorScheme('light')
  const next = scheme === 'dark' ? 'light' : 'dark'
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <ActionIcon variant="default" size="lg" aria-label={`Switch to ${next} mode`} onClick={() => setColorScheme(next)}>
        {scheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  )
}

/** Application frame: slim header with role-aware navigation; pages render in the main area. */
export function Shell() {
  const [drawerOpen, drawer] = useDisclosure(false)

  return (
    <AppShell header={{ height: 48 }} padding="lg">
      <AppShell.Header px="lg">
        <Group h="100%" justify="space-between" wrap="nowrap">
          <Group gap="xl" wrap="nowrap">
            <Burger opened={drawerOpen} onClick={drawer.toggle} hiddenFrom="sm" size="sm" aria-label="Open navigation" />
            <NavLink to="/events" style={{ textDecoration: 'none', color: 'inherit' }} aria-label="Tessera home">
              <Logo />
            </NavLink>
            <Group gap={4} visibleFrom="sm" component="nav" aria-label="Primary navigation">
              <NavLinks />
            </Group>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <ColorSchemeToggle />
            {/* 5b: user menu (email, role, sign out) replaces this */}
            <Button variant="default" size="xs" disabled>
              Sign in
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <Drawer opened={drawerOpen} onClose={drawer.close} size="xs" title={<Logo />} hiddenFrom="sm">
        <Stack gap={4} component="nav" aria-label="Mobile navigation">
          <NavLinks onNavigate={drawer.close} />
        </Stack>
      </Drawer>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
