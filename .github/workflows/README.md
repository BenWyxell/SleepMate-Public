# Workflow status

`windows-release.yml` is intentionally an **unsigned CI-only** workflow. It does not create GitHub Releases and it does not request production signing.

The workflow now implements the production-target **MSI architecture** in three GitHub-hosted stages:

1. Windows x64 program-tree/PyInstaller build;
2. MSI generation with GNOME `msitools/wixl` on Ubuntu;
3. Windows `msiexec` install/runtime/uninstall smoke test.

Official binary release publication remains disabled until:

1. the MSI migration is green on the canonical `main` branch;
2. an unsigned public MSI release exists in the same general artifact form that will later be signed;
3. the SignPath Foundation application is accepted;
4. SignPath GitHub trusted-build/origin verification is configured;
5. the production workflow deep-signs required SleepMate-owned PE files and the MSI;
6. the production workflow verifies Authenticode signatures before final hash/manifest generation and publication.

The previous private-repository release workflow is retained for reference only in `docs/windows-release-legacy-private.yml.txt`; it is not an active GitHub Actions workflow.

The legacy Inno Setup source remains reference/migration infrastructure only and is not called by the active workflow.
