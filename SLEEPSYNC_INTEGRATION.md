# SleepSync integration

SleepSync is integrated into SleepMate starting with the 5.1 release line.

- SleepSync appears inside the normal SleepMate shell and keeps its own Overview, Sync, History and Settings tabs.
- Manual and scheduled EzShare synchronization are connected to the real SleepSync backend engine.
- Every successful synchronization can refresh the therapy source and create the full dated SD mirror / ZIP without modifying the source card.
- Automatic synchronization is schedule-driven and actively rescans/reconnects to the saved EzShare Wi-Fi profile instead of relying on one passive network wait.
- SleepSync uses the SleepMate updater and release lifecycle; there is no separate embedded self-updater.
- Mobile/PWA integration is deliberately isolated until the original SleepMate core has completed boot, protecting the proven Dashboard and navigation startup path.
- The SleepMate service worker and iOS Web Push lifecycle are validated separately because they are critical to remote PWA use.
