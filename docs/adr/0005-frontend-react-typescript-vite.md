# ADR 0005: Frontend as a React + TypeScript SPA (Vite, Mantine, TanStack Query, React Router)

- **Status:** Accepted
- **Date:** 2026-11-28

## Context

The frontend has three areas (attendee portal, organiser console, staff scanner) with sign-in
state, role-dependent views and, later, QR scanning. It's hosted as static files on S3 +
CloudFront (ADR 0001), so it must build to plain HTML/JS/CSS with no server. Each backend
service publishes an OpenAPI spec generated from its code.

## Decision

- **React 19 + TypeScript, built with Vite.** It produces a static single-page app (SPA) in
  `frontend/dist/` for S3. Vite also gives a fast dev server on `localhost:5173`.
- **TypeScript 5.9, pinned.** create-vite now defaults to TypeScript 7 (the native compiler),
  but tools that use the compiler's JavaScript API, including `openapi-typescript`, still
  require TypeScript 5. Revisit when they support 7.
- **API types are generated from each service's `openapi.yaml`** with `openapi-typescript`
  (`npm run gen:api`), and called through `openapi-fetch`, a ~6 KB typed `fetch` wrapper.
  Paths, parameters, bodies and responses are compile-time checked against the backend's
  spec. `npm run check:api` fails if the generated file is out of date.
- **Configuration comes from `VITE_*` variables** in a gitignored `.env.local`, generated
  from SSM, so no account-specific IDs are committed. Everything in the bundle is public, so
  it never holds secrets.
- **UI components: Mantine 9,** themed from a design study (`docs/design/ui-style.md`): blue
  palette, Plus Jakarta Sans + JetBrains Mono (self-hosted via `@fontsource`), Tabler icons.
- **Server data: TanStack Query** (caching, loading/error states, refetch after changes).
- **Routing: React Router** (declarative mode). The selected item is part of the URL, so the
  split view's detail pane survives refresh and works with the back button.
- **Layout: one app with role-aware navigation, built on a split view** (list + detail pane)
  so space is used for content rather than left empty.
- **Times are shown in the viewer's local time with the zone offset;** events have no venue
  time zone yet.
- **Code is organised in feature folders** (`src/features/events`, `src/features/organiser`, …).
- **Tests:** Vitest with Testing Library in a jsdom (simulated browser) environment.
  **Lint:** oxlint, with warnings treated as errors.

## Alternatives considered

- **Plain HTML/JS:** no build step, but state (auth, roles, forms, lists) would need
  hand-rolled structure, and nothing checks API usage against the spec.
- **React + JavaScript:** fewer concepts at once, but API responses wouldn't be type-checked.
- **Next.js or another server-rendering framework:** needs a server (or a static-export mode
  with caveats). That's unnecessary for an app behind sign-in, and it complicates S3 hosting.
- **Hand-written API types:** these drift silently from the backend; generated types fail at
  compile time instead.
- **Styling with plain CSS, Tailwind or shadcn/ui:** plain CSS means hand-building every
  component; Tailwind and shadcn give design control but no ready-made accessible form,
  table, date and modal components. Mantine provides those with theming.
- **TanStack Router:** fully type-safe routes and search params, but much less widely used than
  React Router, which is the industry standard.
- **Plain `useEffect` data fetching:** no library, but loading, error and refresh logic would be
  repeated in every page.

## Consequences

- **Node/npm is part of the toolchain** (`frontend/package.json`, `package-lock.json`).
- **Backend API changes reach the frontend explicitly:** regenerate the spec, run
  `npm run gen:api`, then fix compile errors.
- **One app serves all three role areas;** the server still enforces every role and ownership
  check (CLAUDE.md), and the UI only hides what a role can't use.
