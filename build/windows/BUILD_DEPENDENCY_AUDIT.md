# Windows build dependency audit — SleepMate 5.2.16

This file records the exact additional Python build/test packages resolved by the successful public SleepMate 5.2.16 Windows build (`33438926540`) on CPython 3.13.15 x64. Runtime packages are documented separately in `THIRD_PARTY_NOTICES.md` and `requirements-runtime.lock`.

| Package | Version | License | Exact release/source metadata |
|---|---:|---|---|
| altgraph | 0.17.5 | MIT | https://pypi.org/project/altgraph/0.17.5/ |
| iniconfig | 2.3.0 | MIT | https://pypi.org/project/iniconfig/2.3.0/ |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://pypi.org/project/packaging/26.3/ |
| pefile | 2024.8.26 | MIT | https://pypi.org/project/pefile/2024.8.26/ |
| pluggy | 1.6.0 | MIT | https://pypi.org/project/pluggy/1.6.0/ |
| Pygments | 2.21.0 | BSD-2-Clause | https://pypi.org/project/Pygments/2.21.0/ |
| pyinstaller | 6.22.2 | GPL-2.0 with PyInstaller bootloader exception; selected upstream files Apache-2.0 | https://pypi.org/project/pyinstaller/6.22.2/ |
| pyinstaller-hooks-contrib | 2026.7 | GPL-2.0-or-later for standard hooks; Apache-2.0 for runtime hooks | https://pypi.org/project/pyinstaller-hooks-contrib/2026.7/ |
| pytest | 9.1.1 | MIT | https://pypi.org/project/pytest/9.1.1/ |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | https://pypi.org/project/pywin32-ctypes/0.2.3/ |
| setuptools | 84.0.0 | MIT | https://pypi.org/project/setuptools/84.0.0/ |

## Other release toolchain components

- **CPython 3.13.15 x64** — Python Software Foundation license.
- **pip 26.2.1** — pinned by `build_release.ps1` so the package resolver itself is not silently upgraded during release builds.
- **GNOME msitools / wixl** — used only on the GitHub-hosted Ubuntu MSI job. Upstream is mixed-license: the main library is LGPL-2.1-or-later, while some tools/files use GPL and other upstream licenses. The exact Ubuntu package versions are captured by the workflow in `build-msi-toolchain.txt`.
- **GitHub-hosted Windows/Ubuntu runner system packages** — build infrastructure, not SleepMate-owned redistributed source components.

## PyInstaller distribution note

PyInstaller's official 6.22.2 licensing documentation explicitly permits distributing application bundles generated from application source under the application's chosen license, provided the application respects the licenses of the dependencies it includes. SleepMate does not distribute modified PyInstaller source as its own project code.

## Audit result

The locked Python runtime and build/test dependency sets used for the v5.2.16 public MSI-form release consist of open-source components. No proprietary Python package is intentionally selected by either Windows dependency lock.

Any change to either lock file requires this audit and `THIRD_PARTY_NOTICES.md` to be reviewed again before a production signing request.
