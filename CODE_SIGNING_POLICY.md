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
- the official Windows installer package

Third-party/upstream executables and DLLs are **not** to be re-signed with the SleepMate certificate. Existing valid upstream signatures should be preserved where available; unsigned upstream open-source libraries may be included where permitted by SignPath Foundation policy.

## Installer and uninstaller policy

The production signing target is an **MSI-based installer**.

Reason: SignPath supports Authenticode signing of MSI packages and deep signing of project-owned PE files contained by supported composite packages. Windows uninstall then uses the Microsoft-signed Windows Installer (`msiexec.exe`) instead of relying on a project-generated unsigned `unins*.exe` binary.

The existing Inno Setup installer remains legacy build infrastructure and must not be treated as the final SignPath Foundation release format until the migration is complete.

## Trusted build and origin verification

Official signing requests must originate from GitHub Actions using GitHub-hosted runners. The SignPath GitHub trusted build integration must be used so SignPath can verify repository, branch, commit and workflow origin.

Unsigned input artifacts must be uploaded as GitHub Actions artifacts before a signing request is submitted.

No production signing request may originate from a developer workstation or an unverified manually assembled binary.

## Release branches and approval

Official releases are built from the canonical default branch or an explicitly approved release ref.

Every production signing request requires manual approval in SignPath before the signed artifact is released.

A release must not be published if:

- source/publication security checks fail;
- required tests fail;
- the build does not come from the canonical GitHub Actions workflow;
- SignPath origin verification fails;
- any required SleepMate-owned executable is unsigned;
- the installer signature is missing or invalid;
- product metadata is inconsistent across project-owned signed binaries;
- release hashes/manifests do not match the final signed output.

## Product metadata

All SleepMate-owned signed PE/MSI artifacts must use consistent metadata:

- Product name: `SleepMate`
- Product version: exactly the application release version
- File/product description: clearly identifies the SleepMate component

The release pipeline must verify metadata before publication.

## Post-signing integrity

Signed binaries must never be modified after signing. Packaging, hash generation and release manifest generation must be ordered so that hashes always refer to the final signed artifacts.

## Privacy policy

SleepMate's privacy policy is published in [PRIVACY.md](PRIVACY.md).

Normal local operation is designed not to transfer therapy/health data to the SleepMate developer. Optional network integrations are initiated and configured by the user and are documented in the privacy policy.

## System changes and optional software

Installation and optional integration setup must clearly tell users what system changes are requested. Optional integrations must remain optional and user-controlled.

## Uninstallation

Official packaged builds must provide a standard Windows uninstall path. The target MSI format is intended to use Windows Installer for this purpose.

## Policy changes

Changes to this file, release workflows, build scripts, installer definitions or SignPath-related configuration are security-sensitive and must receive the same review attention as application source changes.

