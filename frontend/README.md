# Frontend

React + TypeScript single-page app built with Vite, Mantine, TanStack Query and React Router
([ADR 0005](../docs/adr/0005-frontend-react-typescript-vite.md)). Look and feel:
[docs/design/ui-style.md](../docs/design/ui-style.md). Hosted later on S3 + CloudFront.

- **Attendee portal:** browse events, reserve, pay (mock), view tickets.
- **Organiser console:** create and manage own events, view analytics (Phase 3).
- **Staff scanner page:** validate tickets at entry (QR in Phase 2).

## Status

- [x] 5a: app shell, theme, split-view layout, routes, mosaic covers, typed Catalogue client;
      pages use **sample data** (`src/features/events/fixtures.ts`) until 5c/5d
- [x] 5b-1: public browsing + CORS on the API
- [x] 5b-2: Cognito login page, OAuth settings, self sign-up; config from SSM
- [x] 5b-3: sign-in in the app (hosted login page, PKCE), user menu, role-aware navigation
- [ ] 5c: browse + event details from the live API
- [ ] 5d: organiser console (create, edit, publish) on the live API
- [ ] 5e: Unsplash cover photos (backend proxy, picker, attribution)

## Commands (PowerShell, from this folder)

```powershell
# once per deployment: writes .env.local from SSM
$env:AWS_PROFILE = "tessera-dev"; ..\scripts\frontend-env.ps1

npm install
npm run dev          # http://localhost:5173
npm test             # Vitest (jsdom)
npm run lint         # oxlint, warnings fail
npm run typecheck    # tsc
npm run build        # static site in dist/
npm run gen:api      # regenerate src/api/catalogue.schema.ts after the Catalogue API changes
npm run check:api    # fails if the generated types are out of date
```

## Layout

| Path | Purpose |
|---|---|
| `src/main.tsx` | Entry point: fonts, Mantine styles, router, providers |
| `src/app/` | `App.tsx` (routes), `Shell.tsx` (header, navigation), `AppProviders.tsx`, `theme.ts` |
| `src/components/` | Shared UI: `SplitView` (list + detail pane), `MosaicCover`, `Logo` |
| `src/features/events/` | Browse page, event detail, status badge, sample data |
| `src/features/organiser/` | My events (table, filters, row actions) and the create/edit form |
| `src/features/errors/` | 404 page |
| `src/lib/` | `datetime.ts` (local time + zone), `mosaic.ts` (cover pattern) |
| `src/api/catalogue.schema.ts` | **Generated** Catalogue API types; don't edit by hand |
| `src/api/catalogue.ts` | Typed `openapi-fetch` client; adds an `X-Correlation-Id` to every request and, via `bearerToken`, the access token when signed in |
| `src/auth/` | Sign-in: `session.ts` (the `Session` interface components use), `oidc.ts` (Cognito settings), `OidcSessionProvider` (library bridge, silent refresh, sign-out), `AuthCallbackPage`, `RequireOrganiser` |
| `src/app/AccountControls.tsx` | Header: Sign in + privacy note, or the user menu |
| `src/config.ts` | Reads and validates `VITE_*` settings: `.env.local` (gitignored) is written by `scripts/frontend-env.ps1` from SSM; names in `.env.example` |
| `src/test/` | Test setup (browser API stubs) and `renderAt` helper |
