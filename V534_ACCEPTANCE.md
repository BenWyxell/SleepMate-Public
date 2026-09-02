# SleepMate v5.3.4 acceptance contract

This branch is not releasable until the following user-facing behaviours are validated against the exact packaged commit.

## P0 – stability and navigation

- The PWA/browser runtime becomes ready on the first real load without a renderer hang or self-triggering settings observer loop.
- Stale SleepMate service-worker caches are recovered without restoring an obsolete frontend generation.
- Repeated Dashboard ↔ Oximetria navigation does not duplicate pages, charts or runtime owners.
- Repeated Fókusz nézet ↔ Összes grafikon ↔ Oximetria switching does not leak interactions or mutate control labels.
- Persistent O₂ canvases must not accumulate duplicate pointer/wheel interaction listeners across repeated peer-mode or Oximetria-tab switching; packaged Edge acceptance must count actual listener registrations before and after the stress loop.
- Fókusz nézet, Összes grafikon and Oximetria are persistent peer modes: entering Oximetria must not hide the controls needed to switch directly to either CPAP chart mode, and the shared peer-mode host must not duplicate across navigation or refresh.
- Mobile Oximetria navigation works through the real mobile drawer and the application itself closes the drawer and scrim after selection; the acceptance test must not close them on the application's behalf.

## Live O₂ lifecycle

- Live O₂ streaming and chart repainting are active only while the visible Oximetria / Élő O₂ monitor view is active.
- Leaving Oximetria closes the live SSE, aborts any in-flight live-buffer refill and does not perform live-buffer refill work in the background; route departure itself must disable Live immediately, even before the outgoing page loses its active DOM class.
- Returning to Oximetria restores the missed interval with one bounded batch request and resumes the live stream without a hand-off gap.
- Intentional lifecycle closure of `/api/o2ring/live-stream` may surface in Edge as `net::ERR_ABORTED`; packaged acceptance may ignore only that exact Live SSE abort, while every other browser request failure remains release-blocking.
- O₂/SleepSync invalidation SSE reconnects must resume from the greater of the explicit `after` cursor and the browser-standard `Last-Event-ID`; every invalidation frame must carry its own SSE `id`, retained replay must stay bounded and ordered, and a normal backend restart must seed a sequence newer than the previous runtime instead of rewinding the PWA cursor.
- Background SleepSync/O2 invalidation remains event-driven so completed therapy imports can update the relevant views without frontend polling.

## O₂ charts

- Live, recording, trend, daily Dashboard, Fókusz, Összes grafikon and Dashboard summary O₂ charts expose an exact HH:MM:SS hover crosshair/tooltip with the value of each displayed series.
- O₂ chart zoom/pan interactions work with mouse/touch interaction contracts and reset cleanly; the packaged Edge gate must exercise both the shared two-finger pinch handler and a one-finger horizontal touch-pan on a zoomed O₂ window rather than relying only on source markers.
- A one-finger touch-pan must move the time-window centre without changing its zoom span, and the interactive canvas must keep `touch-action: pan-y` so vertical page scrolling remains delegated to the browser.
- Pointer-based browser acceptance must interact with an actually visible chart target (scrolling an off-screen canvas into the viewport as a user would) instead of forcing events onto hidden/off-screen controls.
- Interactive O₂ canvases inside the Összes grafikon stack must override the legacy CPAP base-canvas `pointer-events:none` rule; SpO₂, pulse and combined Stack O₂ charts must all remain real pointer/touch targets and pass packaged hover interaction.
- The daily Dashboard O₂ canvases zoom synchronously, while Fókusz and Összes grafikon retain their own zoom ranges when switching between the peer modes.
- Crosshair redraw is requestAnimationFrame-coalesced to avoid pointer-move render storms, and synchronized canvases sharing one redraw function invoke that function at most once per frame.
- High-frequency SpO₂ / pulse charts must split the actually rendered canvas path across a long no-data interval; no line may visually bridge an O₂ gap merely because valid samples exist on both sides.
- CPAP-aligned O₂ overlays must also split their actually rendered SpO₂ and pulse paths across a long O₂ no-data interval while remaining aligned to the therapy time range.
- Daily/nightly O₂ trend series use a day-scale gap policy so valid consecutive nightly points form a continuous rendered trend path instead of being split by the high-frequency live-sample gap rule; the packaged gate must wait for a fresh trend canvas render rather than accepting stale chart metadata from an earlier tab visit.
- The per-chart CPAP O₂ overlay supports off / SpO₂ / pulse / both, persists the choice, displays independent SpO₂ and pulse scales, and shows exact-time O₂/HR hover data.

## Matching and automatic refresh

- CPAP ↔ O2Ring pairing uses real timestamp overlap, deterministic strongest-overlap selection, split-session support and timestamp deduplication.
- Turning automatic matching off truly disables automatic pairing.
- SleepSync completion publishes targeted invalidation for affected days; only a small deterministic recent-day fallback is allowed when changed days cannot be determined.
- A completed SleepSync import must update the currently visible matching O₂/CPAP daily charts and night O₂ summary automatically without requiring a manual refresh.
- The Dashboard O₂ aggregate and mini trends must hydrate from matched O₂ nights in the packaged frontend, not only exist as source-level markup.
- Reports must populate SpO₂ average/minimum, average pulse, T90 and ODI3/ODI4 from matched nightly O₂ data, and an active Reports view must refresh those cells after SleepSync invalidation without a manual refresh.

## Settings and responsive UI

- PWA/notification settings are a single category; no duplicate legacy PWA category returns.
- O2Ring settings are a single responsive category and first-interaction toggle changes persist.
- The first-run wizard reopen card is not duplicated.
- Oximetria and O2Ring settings have no horizontal overflow at iPhone portrait and landscape sizes.
- The latest-session dashboard card never flashes the legacy “Befejezve” status; packaged Edge acceptance must observe the actual `latestStatus` DOM mutation history during first boot, stale-cache recovery and repeated navigation so a transient legacy flash fails the gate even if the final text is correct.

## Release gate

A release may only be created from the same commit that passes:

1. source/contracts and syntax checks, including the resumable invalidation SSE contract,
2. exact-SHA Windows portable build,
3. Hungarian MSI build and real install/smoke test,
4. VERIFIED release-set hash/identity checks,
5. real Microsoft Edge acceptance against that VERIFIED portable artifact, including data-backed O₂ chart interactions, persistent peer-mode switching, Stack O₂ pointer/touch input, two-finger pinch, one-finger touch-pan, listener-stability stress, rendered gap/continuity behaviour, transient latest-session status history and SleepSync invalidation behaviour.

A source-level marker or a green test with no O₂ data is not sufficient proof for a behavioural acceptance item.
