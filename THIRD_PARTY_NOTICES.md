# SleepMate third-party notices

This document records the open-source third-party Python runtime components and the principal build tools used for the SleepMate **5.3.0 Windows release**.

Reference release: `v5.3.0`  
Runtime lock: `build/windows/requirements-runtime.lock`  
Build lock: `build/windows/requirements-build.lock`

SleepMate itself is licensed under `AGPL-3.0-only`. Third-party components are **not relicensed** under the SleepMate license; each remains subject to its own upstream license and copyright notices.

The table below reflects the exact locked Python runtime environment used by the v5.3.0 Windows release pipeline. Exact source distributions/wheels and upstream metadata can be obtained from the linked PyPI release pages.

## Runtime components shipped with the Windows application

| Component | Version | License | Exact release/source metadata |
|---|---:|---|---|
| aiohappyeyeballs | 2.7.1 | PSF-2.0 | https://pypi.org/project/aiohappyeyeballs/2.7.1/ |
| aiohttp | 3.14.3 | Apache-2.0 AND MIT | https://pypi.org/project/aiohttp/3.14.3/ |
| aiosignal | 1.4.0 | Apache-2.0 | https://pypi.org/project/aiosignal/1.4.0/ |
| annotated-types | 0.8.0 | MIT | https://pypi.org/project/annotated-types/0.8.0/ |
| anyio | 4.14.2 | MIT | https://pypi.org/project/anyio/4.14.2/ |
| attrs | 26.1.0 | MIT | https://pypi.org/project/attrs/26.1.0/ |
| bleak | 3.0.2 | MIT | https://pypi.org/project/bleak/3.0.2/ |
| certifi | 2026.7.22 | MPL-2.0 | https://pypi.org/project/certifi/2026.7.22/ |
| cffi | 2.1.1 | MIT-0 | https://pypi.org/project/cffi/2.1.1/ |
| charset-normalizer | 3.5.1 | MIT | https://pypi.org/project/charset-normalizer/3.5.1/ |
| colorama | 0.4.6 | BSD-3-Clause | https://pypi.org/project/colorama/0.4.6/ |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause | https://pypi.org/project/cryptography/50.0.1/ |
| distro | 1.9.0 | Apache-2.0 | https://pypi.org/project/distro/1.9.0/ |
| frozenlist | 1.8.0 | Apache-2.0 | https://pypi.org/project/frozenlist/1.8.0/ |
| groq | 1.7.0 | Apache-2.0 | https://pypi.org/project/groq/1.7.0/ |
| h11 | 0.16.0 | MIT | https://pypi.org/project/h11/0.16.0/ |
| http-ece | 1.2.1 | MIT | https://pypi.org/project/http-ece/1.2.1/ |
| httpcore | 1.0.9 | BSD-3-Clause | https://pypi.org/project/httpcore/1.0.9/ |
| httpx | 0.28.1 | BSD-3-Clause | https://pypi.org/project/httpx/0.28.1/ |
| idna | 3.19 | BSD-3-Clause | https://pypi.org/project/idna/3.19/ |
| multidict | 6.7.1 | Apache-2.0 | https://pypi.org/project/multidict/6.7.1/ |
| Pillow | 12.3.0 | MIT-CMU | https://pypi.org/project/Pillow/12.3.0/ |
| propcache | 0.5.2 | Apache-2.0 | https://pypi.org/project/propcache/0.5.2/ |
| py-vapid | 1.9.4 | MPL-2.0 | https://pypi.org/project/py-vapid/1.9.4/ |
| pycparser | 3.0 | BSD-3-Clause | https://pypi.org/project/pycparser/3.0/ |
| pydantic | 2.13.5 | MIT | https://pypi.org/project/pydantic/2.13.5/ |
| pydantic-core | 2.46.5 | MIT | https://pypi.org/project/pydantic-core/2.46.5/ |
| pystray | 0.19.5 | LGPL-3.0-or-later | https://pypi.org/project/pystray/0.19.5/ |
| pywebpush | 2.5.0 | MPL-2.0 | https://pypi.org/project/pywebpush/2.5.0/ |
| qrcode | 8.2 | BSD-3-Clause | https://pypi.org/project/qrcode/8.2/ |
| reportlab | 5.0.1 | BSD (upstream license) | https://pypi.org/project/reportlab/5.0.1/ |
| requests | 2.34.2 | Apache-2.0 | https://pypi.org/project/requests/2.34.2/ |
| six | 1.17.0 | MIT | https://pypi.org/project/six/1.17.0/ |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | https://pypi.org/project/sniffio/1.3.1/ |
| typing-extensions | 4.16.0 | PSF-2.0 | https://pypi.org/project/typing-extensions/4.16.0/ |
| typing-inspection | 0.4.4 | MIT | https://pypi.org/project/typing-inspection/0.4.4/ |
| urllib3 | 2.7.0 | MIT | https://pypi.org/project/urllib3/2.7.0/ |
| winrt-runtime | 3.2.1 | MIT | https://pypi.org/project/winrt-runtime/3.2.1/ |
| winrt-Windows.Devices.Bluetooth | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Devices.Bluetooth/3.2.1/ |
| winrt-Windows.Devices.Bluetooth.Advertisement | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Devices.Bluetooth.Advertisement/3.2.1/ |
| winrt-Windows.Devices.Bluetooth.GenericAttributeProfile | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Devices.Bluetooth.GenericAttributeProfile/3.2.1/ |
| winrt-Windows.Devices.Enumeration | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Devices.Enumeration/3.2.1/ |
| winrt-Windows.Devices.Radios | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Devices.Radios/3.2.1/ |
| winrt-Windows.Foundation | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Foundation/3.2.1/ |
| winrt-Windows.Foundation.Collections | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Foundation.Collections/3.2.1/ |
| winrt-Windows.Storage.Streams | 3.2.1 | MIT | https://pypi.org/project/winrt-Windows.Storage.Streams/3.2.1/ |
| yarl | 1.24.5 | Apache-2.0 | https://pypi.org/project/yarl/1.24.5/ |

### O2Ring / Windows BLE runtime notes

- **Bleak 3.0.2** is the cross-platform Python BLE client used by SleepMate's O2Ring integration. Upstream declares the `MIT` license.
- On Windows, Bleak resolves the required **PyWinRT 3.2.1** runtime and Windows namespace projection packages listed above. Those PyWinRT packages declare the `MIT` license and remain upstream components; SleepMate does not relicense them.
- SleepMate's O2Ring protocol integration code is part of the SleepMate source tree. It does not bundle or copy source code from the Wellue/Viatom mobile applications or proprietary vendor applications.

### Clarifications

- **Pillow / MIT-CMU:** Pillow 12.3.0 declares the SPDX license expression `MIT-CMU`. The Open Source Initiative approved MIT-CMU as an OSI Certified license in 2024.
- **qrcode 8.2:** the PyPI project page may expose a legacy/confusing `Other/Proprietary License` classifier. Upstream project metadata declares `BSD-3-Clause`; SleepMate uses that upstream license declaration and does not classify qrcode as proprietary software.
- **pystray 0.19.5:** upstream source headers state GNU Lesser General Public License version 3 **or later**. The exact corresponding source is available from the PyPI source distribution linked above and from the upstream repository. SleepMate does not modify or relicense pystray.
- Python packages may contain their own copyright notices, license files, data files, or bundled subcomponents. Those upstream notices remain applicable in addition to this summary.

## Build/test tools not shipped as SleepMate-owned application components

The following tools participate in producing or testing the Windows release but are not relicensed as SleepMate code:

| Tool | Version used for the v5.3.0 release | License / role |
|---|---:|---|
| CPython | 3.13.15 x64 | Python Software Foundation license; build/runtime interpreter packaged by PyInstaller |
| PyInstaller | 6.22.2 | GPL-2.0 with the official PyInstaller bootloader exception; selected upstream files are Apache-2.0. PyInstaller explicitly permits distribution of bundles generated from application source, subject to dependency licenses. |
| pyinstaller-hooks-contrib | 2026.7 | PyInstaller build support; build-time hooks |
| pytest | 9.1.1 | MIT; test-only |
| WiX Toolset | 3.14.1.20250415 | Microsoft Reciprocal License (MS-RL); GitHub-hosted Windows build tool used to generate and inspect the Hungarian MSI. WiX is not shipped as a SleepMate-owned runtime component. |

The release workflow pins WiX Toolset 3.14 and records the exact Python environment from the runtime/build lock files. Build tools remain subject to their upstream licenses and notices.

## System libraries

Windows system components and libraries supplied by the operating system are not SleepMate third-party application components and are not copied into this notice merely because the application calls their public APIs. Python/PyInstaller may package runtime support files required by the frozen application; their upstream licenses remain controlling.

## Source availability

SleepMate source is available in the canonical public repository:

https://github.com/BenWyxell/SleepMate-Public

For every Python component listed above, the exact release page links to its source distribution and upstream project. If a redistributed copyleft component requires corresponding source, the linked exact-version source distribution is the canonical source reference used by this release record.

## No endorsement / trademarks

Third-party names and trademarks belong to their respective owners. Inclusion in SleepMate does not imply endorsement by those projects or maintainers.

## Audit status

The v5.3.0 Windows runtime set above was reviewed against the exact locked dependency environment used by the release pipeline. Bleak and the Windows PyWinRT projection packages are explicitly included in the notice. No proprietary Python runtime dependency is intentionally included in the locked Windows build environment. This notice must be regenerated and reviewed whenever the dependency locks change.
