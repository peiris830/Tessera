/**
 * Tessera's Mantine theme. Colours, fonts and spacing come from the Stitch design study
 * (docs/design/ui-style.md): a deep Mediterranean blue, blue-tinted neutrals and one amber
 * accent, at normal readable sizes (14px body text).
 */
import { createTheme, type MantineColorsTuple } from '@mantine/core'

// Primary blue. [2] = dark-mode primary (#AEC6FF), [6] = #2167D1, [8] = light-mode primary (#004FAD).
const aegean: MantineColorsTuple = [
  '#eef3ff',
  '#d9e4ff',
  '#aec6ff',
  '#85a8f5',
  '#5e8be8',
  '#3f78dd',
  '#2167d1',
  '#105abf',
  '#004fad',
  '#003f8c',
]

// The single warm accent (the "gold tile"): logo and rare highlights only.
const amber: MantineColorsTuple = [
  '#fff6e6',
  '#ffeccc',
  '#fed899',
  '#fdc361',
  '#fdb244',
  '#f2a033',
  '#c58311',
  '#9a5b00',
  '#7a4800',
  '#5c3500',
]

// Blue-tinted neutrals for light mode (backgrounds, borders, secondary text).
const gray: MantineColorsTuple = [
  '#faf9ff',
  '#f2f3fc',
  '#ededf7',
  '#e1e2eb',
  '#c2c6d5',
  '#a3a7b5',
  '#727784',
  '#424753',
  '#2e3037',
  '#191b22',
]

// Dark-mode surfaces: Mantine uses dark[7] for the page, dark[6] for cards, dark[4] for borders.
const dark: MantineColorsTuple = [
  '#e1e2eb',
  '#c2c6d5',
  '#8c909f',
  '#5d6170',
  '#424753',
  '#32353c',
  '#191b22',
  '#11131a',
  '#0c0e14',
  '#08090d',
]

export const theme = createTheme({
  primaryColor: 'aegean',
  primaryShade: { light: 8, dark: 2 },
  autoContrast: true, // dark text on the light-blue dark-mode buttons
  colors: { aegean, amber, gray, dark },

  fontFamily: '"Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", ui-monospace, monospace',
  headings: {
    fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
    fontWeight: '600',
    sizes: {
      h1: { fontSize: '24px', lineHeight: '30px' },
      h2: { fontSize: '18px', lineHeight: '24px' },
      h3: { fontSize: '16px', lineHeight: '22px' },
    },
  },

  fontSizes: { xs: '12px', sm: '13px', md: '14px', lg: '15px', xl: '18px' },
  lineHeights: { md: '1.45' },
  spacing: { xs: '4px', sm: '8px', md: '12px', lg: '16px', xl: '24px' },
  radius: { xs: '2px', sm: '4px', md: '6px', lg: '8px', xl: '12px' },
  defaultRadius: 'md',

  components: {
    Button: { defaultProps: { size: 'sm' } },
    TextInput: { defaultProps: { size: 'sm' } },
    Textarea: { defaultProps: { size: 'sm' } },
    NumberInput: { defaultProps: { size: 'sm' } },
    Badge: { defaultProps: { radius: 'sm', variant: 'light' } },
    Card: { defaultProps: { withBorder: true, padding: 'lg' } },
  },
})
