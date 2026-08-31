# SignPath configuration notes

The XML in this directory is a **template**, not a production artifact configuration.

After the MSI migration:

1. Build a representative unsigned release artifact on GitHub Actions.
2. Upload that sample in SignPath and let SignPath analyze its structure.
3. Compare the generated configuration with the policy intent in this repository.
4. Exclude upstream/third-party PE files from SleepMate signing.
5. Add metadata restrictions for project-owned files.
6. Store the final artifact-configuration slug in the release workflow/configuration.

Do not activate a production signing workflow until the SignPath Foundation application is accepted and the trusted GitHub build integration is configured.
