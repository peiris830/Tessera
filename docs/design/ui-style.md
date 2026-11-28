# Tessera UI style

How the frontend looks and why. The implementation is `frontend/src/app/theme.ts`; the stack is
in [ADR 0005](../adr/0005-frontend-react-typescript-vite.md).

## Process

1. **Requirements:** a bluish palette, no wasted space, one app for all roles, light and dark
   mode, accessible.
2. **Design study:** Google Stitch generated all screens (sign-in, browse, event details,
   My events, create/edit form, global states) at desktop and mobile sizes, from a prompt
   describing the roles, screens, synthetic data and constraints.
3. **Review:** Stitch's tokens were kept, and its screens were corrected where they disagreed
   with the API (listed below).
4. **Translation into a Mantine theme** (10-shade palettes, CSS variables, component defaults).

## Principles

- **Use space for content, not emptiness.** List + detail **split view**: the selected item
  fills the right pane instead of opening a new page. When nothing is selected, the right
  pane shows a useful summary (counts, next event), never a blank box. Filters, search and
  counts sit above lists.
- **Progressive disclosure:** row actions (Edit, Publish) appear on hover and keyboard focus,
  and always on touch screens.
- **Readable sizes:** 14px body text, ~32px controls, 48px header. "Less whitespace" means
  more useful content, not smaller text.
- **The UI mirrors server rules but never enforces them:** e.g. no Edit on cancelled events,
  capacity locked after publishing. The API remains the authority.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| Primary (`aegean`) | `#004FAD` (shade 8) | `#AEC6FF` (shade 2, dark text) | Buttons, links, focus, selection |
| Primary mid | `#2167D1` (shade 6) | | Dates in lists, logo tile |
| Accent (`amber`) | `#FDB244` | | Logo "gold tile", ~1 in 14 mosaic tiles; never body text |
| Page / surface | `#FAF9FF` / `#FFFFFF` | `#11131A` / `#191B22` | Blue-tinted neutrals |
| Text / secondary | `#191B22` / `#727784` | `#E1E2EB` / `#8C909F` | |
| Status | green (PUBLISHED), gray (DRAFT), red (CANCELLED) | | Light badges, monospace labels |

Contrast: white on `#004FAD` is about 7.6:1, comfortably above WCAG AA (4.5:1).

- **Typography:** **Plus Jakarta Sans** for all text (headings 24/18/16px, 600 weight) and
  **JetBrains Mono** for dates and numbers, with aligned digits. Both are self-hosted from npm,
  so the app makes no request to Google Fonts.
- **Spacing:** 4 / 8 / 12 / 16 / 24 px. **Radius:** 4–6 px (8 px for panels).
- **Icons:** Tabler (outline), imported per icon.

## Event covers

- **Generated mosaic covers** (`MosaicCover`): a tile pattern derived from the event ID, so
  every event is recognisable with no image stored. Tiles use the theme's blues with an
  occasional amber tile, follow dark mode, and are greyed out for cancelled events. Screen
  readers skip them, since they're decoration.
- **Planned (step 5e):** organisers pick an Unsplash photo, searched through a backend proxy
  that keeps the key in SSM. It's shown with the required attribution, and the mosaic stays as
  the fallback. Later, organisers can upload their own photos (S3 presigned uploads).

## Dates and times

Stored in UTC and shown in the **viewer's local time with the zone offset**, e.g.
`12 Jul 2027, 19:30 GMT+5:30`; lists use the short form `12 Jul, 19:30`. Events have no venue
time zone yet. Adding one would mean a Catalogue data model change.

## Corrections to the Stitch screens

| Stitch | Tessera |
|---|---|
| Edit button on cancelled events | Hidden: the API rejects edits with `409 EVENT_NOT_EDITABLE` |
| Capacity disabled on the mobile *create* form | Only locked once published |
| Skeleton grid with 3 columns, loaded grid with 4 | Matching layouts (split-view list) |
| Event details for published events only | Also a cancelled state (attendees can open cancelled events) |
| "Preview state" tab bars | Design-tool artefacts, removed |
| Realistic-looking sample names | Synthetic `@example.com` users only |
| Material Symbols icon font, three web fonts | Tabler icons, two self-hosted fonts |
