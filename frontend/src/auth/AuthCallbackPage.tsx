import { Alert, Anchor, Center, Loader, Stack, Text } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { useEffect } from 'react'
import { useAuth } from 'react-oidc-context'
import { Link, useNavigate } from 'react-router'
import { safeReturnPath } from './session'

/**
 * Cognito redirects here with ?code=...&state=... AuthProvider exchanges the code for tokens;
 * once that's done, this page replaces itself with the page the user started from (so the
 * code never stays in the address bar or history).
 */
export function AuthCallbackPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const { isLoading, user, error } = auth

  useEffect(() => {
    if (isLoading || error) return
    const state = user?.state as { returnTo?: unknown } | undefined
    navigate(safeReturnPath(state?.returnTo), { replace: true })
  }, [isLoading, user, error, navigate])

  if (error) {
    return (
      <Center mih={240}>
        <Alert color="red" icon={<IconAlertTriangle size={18} />} title="Sign-in didn't complete" maw={480}>
          <Stack gap="xs">
            <Text size="sm">{error.message}</Text>
            <Anchor component={Link} to="/events" size="sm">
              Back to events
            </Anchor>
          </Stack>
        </Alert>
      </Center>
    )
  }
  return (
    <Center mih={240}>
      <Stack align="center" gap="xs">
        <Loader size="sm" />
        <Text size="sm" c="dimmed">
          Signing you in…
        </Text>
      </Stack>
    </Center>
  )
}
