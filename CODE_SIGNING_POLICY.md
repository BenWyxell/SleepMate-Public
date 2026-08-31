# Code signing policy

## Purpose

This policy defines how official SleepMate Windows releases are built and approved for code signing.

**Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).**

The SignPath Foundation subscription is currently being prepared. Until the Foundation application is accepted and the trusted-build integration is configured, no SleepMate binary is represented as SignPath-signed.

## Project and repository

- Project: SleepMate
- Source repository: `BenWyxell/SleepMate-Public` (canonical public source repository for signing)
- Maintained release platform: Windows x64
- Source license: AGPL-3.0-only, except third-party components under their own compatible open-source licenses

## Team roles

The initial project team is a single-maintainer team:

- **Committer / Author:** GitHub user `BenWyxell`
- **Reviewer:** GitHub user `BenWyxell` reviews contributions from users who do not have direct commit access
- **Signing Approver:** GitHub user `BenWyxell`

If additional maintainers are added, this section must be updated before they receive signing-related permissions.

## MFA

All users with repository write access or SignPath signing responsibilities must use multi-factor authentication on both GitHub and SignPath.

## What may be signed

Only SleepMate-owned binaries that are reproducibly built from source and build scripts in the canonical repository may be signed with the SleepMate SignPath Foundation signing configuration.

The intended signing set includes at least:

- `SleepMate.exe`
- `SleepMateUpdater.exe`
- any future SleepMate-owned `.exe` or `.dll` shipped as part of the product
- `SleepMate_Setup_vX.Y.Z.msi`

Third-party/upstream executables and DLLs are **not** to be re-signed with the SleepMate certificate. Existing valid upstream signatures should be preserved where available; unsigned upstream open-source libraries may be included where permitted by SignPath Foundation policy.

## Installer and uninstaller policy

The production signing target is an **MSI-based per-user installer**.

The canonical unsigned MSI is built in GitHub Actions from the exact Windows program tree produced by the preceding GitHub-hosted Windows build job.

The active MSI authoring tool is **GNOME msitools / `wixl`** on a GitHub-hosted Ubuntu runner. `msitools` is a build-time dependency and is not distributed as part of SleepMate. The repository must pin or record the effective build-tool version for production releases.

The existing Inno Setup installer is **legacy-only** infrastructure and must not be used for a production SignPath release.

Windows uninstall uses the Microsoft Windows Installer (`msiexec.exe`). No project-generated `unins*.exe` is part of the MSI release architecture.

## Trusted build and origin verification

Official signing requests must originate from GitHub Actions using GitHub-hosted runners. The SignPath GitHub trusted build integration must be used so SignPath can verify repository, branch, commit and workflow origin.

Unsigned input artifacts must be uploaded as GitHub Actions artifacts before a signing request is submitted.

No production signing request may originate from a developer workstation or an unverified manually assembled binary.

Repository PFX files, developer workstation certificates and ad-hoc PFX GitHub secrets are not part of the production signing design.

## Build stages

The unsigned production candidate is assembled in explicit stages:

1. GitHub-hosted Windows runner builds `SleepMate.exe`, `SleepMateUpdater.exe`, the application tree and portable update ZIP.
2. The exact application tree is uploaded as a GitHub Actions artifact.
3. A GitHub-hosted Ubuntu runner generates the deterministic MSI authoring source and builds `SleepMate_Setup_vX.Y.Z.msi`.
4. A GitHub-hosted Windows runner installs the MSI with `msiexec`, starts the installed application, verifies required runtime APIs, uninstalls with `msiexec`, and verifies that program files are removed while user state is preserved.
5. Only artifacts that passed these gates may be supplied to the SignPath signing stage.

## Release branches and approval

Official releases are built from the canonical default branch or an explicitly approved release ref.

Every production signing request requires manual approval in SignPath before the signed artifact is released.

A release must not be published if:

- source/publication security checks fail;
- required tests fail;
- the MSI install/runtime/uninstall smoke test fails;
- the build does not come from the canonical GitHub Actions workflow;
- SignPath origin verification fails;
- any required SleepMate-owned executable is unsigned;
- the MSI signature is missing or invalid;
- product metadata is inconsistent across project-owned signed binaries;
- release hashes/manifests do not match the final signed output.

## Product metadata

All SleepMate-owned signed PE/MSI artifacts must use consistent metadata:

- Product name: `SleepMate`
- Product version: exactly the application release version
- File/product description: clearly identifies the SleepMate component
- MSI manufacturer/publisher text: the project publisher defined in the canonical source

The release pipeline must verify metadata before publication.

## MSI identity and upgrades

The MSI must use:

- one stable UpgradeCode for the SleepMate product family;
- a deterministic ProductCode derived from the application version;
- a PackageCode derived from the version and exact payload content;
- per-user installation under `%LOCALAPPDATA%\Programs\SleepMate`;
- major-upgrade semantics that reject downgrades.

The MSI must not delete `%LOCALAPPDATA%\SleepMate` user therapy/profile state during uninstall.

## Post-signing integrity

Signed binaries must never be modified after signing.

For production releases:

1. signing occurs before final release hash generation;
2. the final update ZIP must contain the final signed SleepMate-owned executables;
3. the final MSI must contain the final signed SleepMate-owned executables and must itself be signed;
4. the release manifest and SHA-256 files are generated only from the final signed outputs.

## Privacy policy

SleepMate's privacy policy is published in [PRIVACY.md](PRIVACY.md).

Normal local operation is designed not to transfer therapy/health data to the SleepMate developer. Optional network integrations are initiated and configured by the user and are documented in the privacy policy.

## System changes and optional software

The MSI installs SleepMate itself.

Optional integrations such as Tailscale or cloudflared must remain optional and user-controlled. The production MSI must not silently bootstrap unrelated development tools or package managers.

## Uninstallation

Official packaged builds must provide a standard Windows uninstall path through Windows Installer.

Removing the application must not remove the user's separate SleepMate therapy/profile state unless the user explicitly requests a data deletion operation outside the normal MSI uninstall path.

## Policy changes

Changes to this file, release workflows, build scripts, MSI generator/authoring source, installer definitions or SignPath-related configuration are security-sensitive and must receive the same review attention as application source changes.
