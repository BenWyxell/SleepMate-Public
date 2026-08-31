# Contributing to SleepMate

Contributions are welcome through GitHub pull requests.

## Before submitting

- Do not include real patient/therapy data.
- Do not include real API keys, OAuth tokens, credentials or private keys.
- Do not include user-specific paths such as `C:\Users\<real-user>\...`.
- Use synthetic fixtures and clearly artificial identifiers.
- Keep optional external integrations opt-in.
- Do not add proprietary or non-open-source components to distributed builds without prior license review.

## Security-sensitive files

Changes to the following areas require particular care:

- `.github/workflows/`
- `build/`
- installer/update code
- `.signpath/`
- secret stores / authentication code
- Web Push / remote access / cloud integrations

External contributions are reviewed by a project maintainer before merge.

## License of contributions

By submitting a contribution, you agree that your contribution is provided under the project's AGPL-3.0-only license unless explicitly agreed otherwise for a third-party file that already carries its own compatible license.

