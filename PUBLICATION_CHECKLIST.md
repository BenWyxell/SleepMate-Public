# Public publication checklist

The canonical public repository and the first public MSI-form Windows candidate are live. This checklist tracks the remaining requirements for the SignPath Foundation application and later production signing activation.

## Blocking items before SignPath Foundation application

- [x] Fill the publisher/controller contact placeholders in `PRIVACY.md` section 2 with accurate information.
- [x] Confirm GitHub MFA is enabled for all maintainers with write access. Manually confirmed by the maintainer on 2026-08-31.
- [x] Confirm the canonical public repository starts from this clean snapshot and **does not import the old private Git history**.
- [x] Run `python scripts/verify_public_source.py` and require PASS.
- [x] Confirm no personal therapy files, `config.json`, `private/`, backups, logs, DBs or credentials are present.
- [x] Review third-party runtime and build dependency licenses for the exact versions used by the first public binary build; record them in `THIRD_PARTY_NOTICES.md`, `build/windows/requirements-runtime.lock`, `build/windows/requirements-build.lock`, and `build/windows/BUILD_DEPENDENCY_AUDIT.md`.
- [x] Enable GitHub private vulnerability reporting. Manually confirmed by the maintainer on 2026-08-31.

## SignPath Foundation preparation

- [x] Public repository exists and is the canonical source repository: `BenWyxell/SleepMate-Public`.
- [x] `README.md` exposes a section named **Code signing policy**.
- [x] `CODE_SIGNING_POLICY.md` remains accurate for the current MSI + GitHub-hosted build architecture.
- [x] Privacy policy is complete in this public source snapshot.
- [x] Team roles are accurate for the current single-maintainer repository.
- [x] GitHub MFA is enabled. SignPath MFA must be enabled as soon as the SignPath account/project is provisioned.
- [x] Public CI/release workflow definitions use GitHub-hosted runners.
- [x] Installer architecture is migrated to the intended SignPath-supported MSI production format and has passed build/install/runtime/uninstall CI.
- [x] A public release exists in the same general MSI form that will later be signed: `v5.2.16` / `SleepMate_Setup_v5.2.16.msi`.
- [x] The one-time unsigned release publisher used only to satisfy the pre-application MSI-release requirement has been removed; normal CI does not publish GitHub Releases.
- [x] Add a visible **Code signing policy** section/link to the `v5.2.16` GitHub Release page, including the required SignPath Foundation attribution and privacy-policy link. Verified on the public release page on 2026-08-31.
- [ ] Submit the SignPath Foundation application.

## Production signing activation

After acceptance:

- [ ] Install/link SignPath GitHub App and predefined GitHub.com trusted build system.
- [ ] Configure SignPath organization/project/signing-policy/artifact-configuration identifiers.
- [ ] Store the SignPath API token as a GitHub Actions secret if required by the selected SignPath integration flow.
- [ ] Require manual approval for each production signing request.
- [ ] Verify Authenticode signature for every SleepMate-owned executable and the installer before release publication.
- [ ] Generate hashes and update manifest only from the final signed files.
- [ ] Generate/publish a release SBOM from the exact signed release environment.
- [x] Maintain exact third-party notices for the current unsigned MSI candidate; regenerate them whenever dependency locks change.
