# SleepMate v5.3.4 acceptance contract

This branch is not releasable until the following user-facing behaviours are validated against the exact packaged commit.

## P0 – stability and navigation

- The PWA/browser runtime becomes ready on the first real load without a renderer hang or self-triggering settings observer loop.
- Stale SleepMate service-worker caches are recovered without restoring an obsolete frontend generation.
- Repeated Dashboard ↔ Oximetria navigation does not duplicate pages, charts or runtime owners.
- Repeated Fókusz nézet ↔ Összes grafikon ↔ Oximetria switching does not leak interactions or mutate control labels.
- Mobile Oximetria navigation works through the real mobile drawer and the application itself closes the drawer and scrim after selection; the acceptance test must not close them on the application's behalf.

## Live O₂ lifecycle

- Live O₂ streaming and chart repainting are active only while the visible Oximetria / Élő O₂ monitor view is active.
- Leaving Oximetria closes the live SSE, aborts any in-flight live-buffer refill and does not perform live-buffer refill work in the background; route departure itself must disable Live immediately, even before the outgoing page loses its active DOM class.
- Returning to Oximetria restores the missed interval with one bounded batch request and resumes the live stream without a hand-off gap.
- Background SleepSync/O2 invalidation remains event-driven so completed therapy imports can update the relevant views without frontend polling.

## O₂ charts

- Live, recording, trend, daily Dashboard, Fókusz, Összes grafikon and Dashboard summary O₂ charts expose an exact HH:MM:SS hover crosshair/tooltip with the value of each displayed series.
- O₂ chart zoom/pan interactions work with mouse/touch interaction contracts and reset cleanly.
- The daily Dashboard O₂ canvases zoom synchronously, while Fókusz and Összes grafikon retain their own zoom ranges when switching between the peer modes.
- Crosshair redraw is requestAnimationFrame-coalesced to avoid pointer-move render storms, and synchronized canvases sharing one redraw function invoke that function at most once per frame.
- Daily O₂ trend series use a day-scale gap policy so valid nightly points form continuous trend lines instead of being split by the high-frequency live-sample gap rule.
- CPAP-aligned O₂ overlays use the same therapy time range and gap-aware timestamp alignment.
- The per-chart CPAP O₂ overlay supports off / SpO₂ / pulse / both, persists the choice, displays independent SpO₂ and pulse scales, and shows exact-time O₂/HR hover data.

## Matching and automatic refresh

- CPAP ↔ O2Ring pairing uses real timestamp overlap, deterministic strongest-overlap selection, split-session support and timestamp deduplication.
- Turning automatic matching off truly disables automatic pairing.
- SleepSync completion publishes targeted invalidation for affected days; only a small deterministic recent-day fallback is allowed when changed days cannot be determined.
- A completed SleepSync import must update the currently visible matching O₂/CPAP daily charts and night O₂ summary automatically without requiring a manual refresh.
- The Dashboard O₂ aggregate and mini trends must hydrate from matched O₂ nights in the packaged frontend, not only exist as source-level markup.

## Settings and responsive UI

- PWA/notification settings are a single category; no duplicate legacy PWA category returns.
- O2Ring settings are a single responsive category and first-interaction toggle changes persist.
- The first-run wizard reopen card is not duplicated.
- Oximetria and O2Ring settings have no horizontal overflow at iPhone portrait and landscape sizes.
- The latest-session dashboard card never flashes the legacy “Befejezve” status; the packaged core owns the session-count presentation.

## Release gate

A release may only be created from the same commit that passes:

1. source/contracts and syntax checks,
2. exact-SHA Windows portable build,
3. Hungarian MSI build and real install/smoke test,
4. VERIFIED release-set hash/identity checks,
5. real Microsoft Edge acceptance against that VERIFIED portable artifact, including data-backed O₂ chart interactions and SleepSync invalidation behaviour.

A source-level marker or a green test with no O₂ data is not sufficient proof for a behavioural acceptance item.
