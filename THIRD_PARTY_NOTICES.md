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

| Component | Role | License |
|---|---|---|
| PyInstaller | Windows packaging | GPL-2.0 with the PyInstaller bootloader exception; selected files also Apache-2.0 |
| pytest | Tests | MIT |
| Inno Setup | Legacy installer builder | Inno Setup License (permissive source/binary redistribution conditions) |

## Planned installer tooling

The SignPath production architecture plans to move away from the legacy Inno Setup executable installer to an MSI-based build so project-owned binaries and the installer can be signed in a SignPath-supported composite format. The exact MSI build tool and its licensing must be reviewed before it becomes a production dependency.

## Upstream binaries

SleepMate's signing policy does not permit re-signing third-party/upstream binaries with the SleepMate SignPath Foundation certificate. Where upstream binaries are included, their own licenses and signatures remain applicable.

## Exact notices

Binary releases may contain transitive Python dependencies and Windows/system components not listed individually above. Before the first public binary release, the release pipeline should generate and publish an exact dependency/SBOM inventory and retain applicable third-party license notices.

