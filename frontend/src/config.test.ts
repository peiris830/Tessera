import { ConfigError, loadConfig } from './config'

const complete = {
  VITE_CATALOGUE_API_URL: 'https://api.example.test/',
  VITE_COGNITO_AUTHORITY: 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example',
  VITE_COGNITO_CLIENT_ID: 'exampleclientid',
  VITE_COGNITO_HOSTED_UI_URL: 'https://tessera-dev-0123abcd.auth.us-east-1.amazoncognito.com/',
}

test('reads the configuration and strips trailing slashes from URLs', () => {
  expect(loadConfig(complete)).toEqual({
    catalogueApiUrl: 'https://api.example.test',
    cognitoAuthority: 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example',
    cognitoClientId: 'exampleclientid',
    cognitoHostedUiUrl: 'https://tessera-dev-0123abcd.auth.us-east-1.amazoncognito.com',
  })
})

test('names every missing variable and how to fix it', () => {
  expect(() => loadConfig({ VITE_COGNITO_CLIENT_ID: 'x' })).toThrow(ConfigError)
  expect(() => loadConfig({})).toThrow(
    /VITE_CATALOGUE_API_URL, VITE_COGNITO_AUTHORITY, VITE_COGNITO_CLIENT_ID, VITE_COGNITO_HOSTED_UI_URL.*frontend-env/,
  )
})

