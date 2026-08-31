# Third-party notices

SleepMate is licensed under AGPL-3.0-only, but it uses and/or is built with third-party open-source software under their own licenses.

This file is a high-level inventory of direct dependencies and build tooling. Exact transitive dependency versions in a binary release should be captured by the release pipeline/SBOM.

## Direct runtime dependencies

| Component | Role | License |
|---|---|---|
| Python / CPython | Runtime | Python Software Foundation License |
| `groq` | Optional Groq API client | Apache-2.0 |
| `pystray` | Windows tray integration | LGPL-3.0 |
| Pillow | Image processing | MIT-CMU |
| ReportLab | PDF generation | BSD-style license |
| `qrcode` | QR-code generation | BSD license |
| `pywebpush` | Web Push | MPL-2.0 |
| `cryptography` | Cryptographic primitives / key handling | Apache-2.0 OR BSD-3-Clause |

## Build and test tooling

| Component | Role | License / status |
|---|---|---|
| PyInstaller | Windows application packaging | GPL-2.0 with the PyInstaller bootloader exception; selected files also Apache-2.0 |
| pytest | Tests | MIT |
| GNOME `msitools` / `wixl` | MSI generation on GitHub-hosted Linux runner | LGPL-2.1-or-later |
| Inno Setup | Legacy installer builder retained for migration/reference only; not used by the active production-target workflow | Inno Setup License |

`msitools` is a build-time dependency and is not shipped as part of the SleepMate application or MSI.

## WiX Toolset note

The active MSI workflow intentionally does not depend on the current WiX Toolset binary releases. Current WiX releases participate in the Open Source Maintenance Fee program, which can impose a maintenance fee for revenue-generating use. The public SleepMate MSI pipeline therefore uses `msitools/wixl` unless the installer-tooling policy is deliberately changed after a separate licensing review.

## Upstream binaries

SleepMate's signing policy does not permit re-signing third-party/upstream binaries with the SleepMate SignPath Foundation certificate. Where upstream binaries are included, their own licenses and signatures remain applicable.

## Exact notices

Binary releases may contain transitive Python dependencies and Windows/system components not listed individually above. Before the first public production binary release, the release pipeline should generate and publish an exact dependency/SBOM inventory and retain applicable third-party license notices.
