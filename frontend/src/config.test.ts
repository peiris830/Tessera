import { ConfigError, loadConfig } from './config'

const complete = {
  VITE_CATALOGUE_API_URL: 'https://api.example.test/',
  VITE_COGNITO_USER_POOL_ID: 'us-east-1_example',
  VITE_COGNITO_APP_CLIENT_ID: 'exampleclientid',
}

test('reads the configuration and strips a trailing slash from the API URL', () => {
  expect(loadConfig(complete)).toEqual({
    catalogueApiUrl: 'https://api.example.test',
    cognitoUserPoolId: 'us-east-1_example',
    cognitoAppClientId: 'exampleclientid',
  })
})

test('names every missing variable and how to fix it', () => {
  expect(() => loadConfig({ VITE_COGNITO_USER_POOL_ID: 'x' })).toThrow(ConfigError)
  expect(() => loadConfig({})).toThrow(
    /VITE_CATALOGUE_API_URL, VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_APP_CLIENT_ID.*frontend-env/,
  )
})
