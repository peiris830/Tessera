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
- [ ] 5b: CORS on the API, Cognito sign-in, role-aware navigation
- [ ] 5c: browse + event details from the live API
- [ ] 5d: organiser console (create, edit, publish) on the live API
- [ ] 5e: Unsplash cover photos (backend proxy, picker, attribution)

## Commands (PowerShell, from this folder)

```powershell
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
| `src/api/catalogue.ts` | Typed `openapi-fetch` client; adds an `X-Correlation-Id` to every request |
| `src/config.ts` | Reads and validates `VITE_*` settings (from `.env.local`, gitignored) |
| `src/test/` | Test setup (browser API stubs) and `renderAt` helper |
