# Public publication checklist

This repository snapshot is prepared for open-source publication, but the following items must be confirmed before changing repository visibility to public.

## Blocking items

- [x] Fill the publisher/controller contact placeholders in `PRIVACY.md` section 2 with accurate information.
- [ ] Confirm GitHub MFA is enabled for all maintainers with write access.
- [x] Confirm the canonical public repository starts from this clean snapshot and **does not import the old private Git history**.
- [x] Run `python scripts/verify_public_source.py` and require PASS.
- [x] Confirm no personal therapy files, `config.json`, `private/`, backups, logs, DBs or credentials are present.
- [ ] Review third-party dependency licenses for the exact versions selected for the first public binary build.
- [ ] Enable GitHub private vulnerability reporting if available.

## SignPath Foundation preparation

- [x] Public repository exists and is the canonical source repository: `BenWyxell/SleepMate-Public`.
- [x] `README.md` exposes a section named **Code signing policy**.
- [ ] `CODE_SIGNING_POLICY.md` remains accurate.
- [x] Privacy policy is complete in this public source snapshot.
- [x] Team roles are accurate for the current single-maintainer repository.
- [ ] SignPath and GitHub MFA enabled.
- [x] Public CI/release workflow definitions use GitHub-hosted runners.
- [ ] Installer architecture is migrated to the SignPath-supported production format.
- [ ] A release exists in the same general form that will later be signed.
- [ ] SignPath Foundation application submitted only after the above are true.

## Production signing activation

After acceptance:

- [ ] Install/link SignPath GitHub App and predefined GitHub.com trusted build system.
- [ ] Configure SignPath organization/project/signing-policy/artifact-configuration identifiers.
- [ ] Store SignPath API token as a GitHub Actions secret.
- [ ] Require manual approval for each production signing request.
- [ ] Verify Authenticode signature for every SleepMate-owned executable and the installer before release publication.
- [ ] Generate hashes and update manifest only from the final signed files.
- [ ] Generate/publish SBOM and exact third-party notices.

