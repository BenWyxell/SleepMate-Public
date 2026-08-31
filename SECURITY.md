# Security Policy

## Supported version

Security fixes are normally applied to the latest maintained SleepMate release.

## Reporting a vulnerability

Please **do not** publish secrets, private patient/therapy data, API keys, OAuth tokens, private network addresses, exploit details or sensitive logs in a public GitHub issue.

Preferred reporting channel:

1. Use GitHub's **private vulnerability reporting / Security Advisory** feature for the SleepMate repository when available.
2. If private reporting is not available, open a minimal public issue stating only that you need a private security contact. Do not include exploit details or sensitive data in that public issue.

## Secrets

Real credentials must never be committed to the repository. Examples include:

- GitHub personal access tokens
- Google OAuth client secrets or refresh/access tokens
- Groq / Gemini / other API keys
- Cloudflare credentials
- private keys, PFX/P12 signing material
- user-specific `config.json` or files under `private/`

Test fixtures must use clearly synthetic values that do not match real credential formats where practical.

## Release security

Official Windows releases are intended to be built on GitHub-hosted runners and, after SignPath Foundation onboarding, signed through a SignPath trusted-build workflow with origin verification and manual signing approval.

See [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

