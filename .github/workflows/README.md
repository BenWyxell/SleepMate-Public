# Workflow status

`windows-release.yml` is intentionally an **unsigned CI-only** workflow in this public-preparation snapshot. It does not create GitHub Releases.

Official binary release publication must remain disabled until:

1. the public repository is canonical,
2. the MSI packaging migration is complete,
3. the SignPath Foundation application is accepted,
4. SignPath GitHub trusted-build/origin verification is configured,
5. the production workflow verifies all required Authenticode signatures before publishing.

The previous private-repository release workflow is retained for reference only in `docs/windows-release-legacy-private.yml.txt`; it is not an active GitHub Actions workflow.
