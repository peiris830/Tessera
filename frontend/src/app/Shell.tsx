import { AppShell, Burger, Button, Drawer, Group, Stack } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { NavLink, Outlet } from 'react-router'
import { type Role, hasRole, useSession } from '../auth/session'
import { Logo } from '../components/Logo'
import { AccountControls } from './AccountControls'

// Links with a role only show for users in that Cognito group (a convenience, not security:
// the organiser routes are guarded and the API enforces roles).
const NAV: { to: string; label: string; role?: Role }[] = [
  { to: '/events', label: 'Browse events' },
  { to: '/organiser/events', label: 'My events', role: 'organiser' },
]

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const session = useSession()
  const visible = NAV.filter((item) => !item.role || hasRole(session, item.role))
  return visible.map((item) => (
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
          <AccountControls />
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
