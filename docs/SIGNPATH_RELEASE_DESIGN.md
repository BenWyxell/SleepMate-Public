# SignPath / Windows release architecture

## Why the current installer is not the final design

The legacy build creates an Inno Setup `.exe` installer. It can sign the outer setup executable, but the project requirement is stricter: every SleepMate-owned executable installed on disk must be signed, and no project-generated unsigned uninstaller should remain.

SignPath Open Source Code Signing requires trusted-build/origin verification and manual approval. SignPath's supported deep-signing composite formats include MSI/MSIX/CAB, but an Inno Setup executable is not listed as a deep-signing container format.

For this reason the production target is **MSI** rather than trying to force the legacy installer into a brittle multi-stage signing workaround.

## Target artifact structure

A GitHub-hosted Windows runner builds unsigned source-derived artifacts:

```text
signing-input.zip
├── SleepMate_Setup_vX.Y.Z.msi
└── SleepMate_vX.Y.Z_windows_x64.zip
    └── SleepMate_vX.Y.Z/
        ├── SleepMate.exe
        ├── SleepMateUpdater.exe
        └── ... upstream/runtime files ...
```

The MSI contains the same SleepMate-owned application executables.

A SignPath artifact configuration should be generated/reviewed from a real MSI sample. It should:

1. Authenticode-sign SleepMate-owned PE files in the portable ZIP.
2. Deep-sign SleepMate-owned PE files in the MSI.
3. Authenticode-sign the MSI itself.
4. Never re-sign upstream DLLs with the SleepMate certificate.
5. Enforce `ProductName=SleepMate` and one consistent release version on signed project-owned files.

## Signing flow

```text
GitHub source commit
  -> GitHub-hosted Actions build
  -> tests + public-source/secret gate
  -> unsigned signing-input artifact uploaded to GitHub Actions
  -> SignPath trusted-build signing request
  -> manual approval
  -> signed artifact returned
  -> Authenticode verification gate
  -> SHA-256 + sleepmate-update.json generated from final signed portable ZIP
  -> smoke install / uninstall test
  -> GitHub Release publication
```

## Uninstall

With MSI, uninstall is performed by Windows Installer (`msiexec.exe`). SleepMate does not need to ship its own `unins000.exe`, eliminating the unsigned custom-uninstaller problem.

## Self-update

The existing in-app updater consumes the portable ZIP named by `sleepmate-update.json`. The future workflow should generate the manifest after signing so the recorded SHA-256 matches the signed ZIP.

When an update replaces `SleepMate.exe` or `SleepMateUpdater.exe`, those files must already carry valid Authenticode signatures in the signed ZIP.

## Avast / antivirus hygiene

Code signing cannot mathematically guarantee that no antivirus product will ever report a false positive. The build should nevertheless minimize heuristic triggers:

- keep PyInstaller onedir packaging;
- keep UPX disabled;
- avoid runtime unpacking/self-modifying tricks;
- avoid encoded/obfuscated script execution;
- keep update sources fixed and integrity-checked;
- sign every SleepMate-owned executable distributed to users;
- use stable product/version metadata;
- avoid unnecessary installer-time system changes;
- keep optional integrations visibly opt-in;
- publish hashes/SBOM/source for every official release.

