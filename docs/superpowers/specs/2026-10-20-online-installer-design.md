# Framewise online installer - approved implementation scope

Date: 2026-10-20. The user approved the online installer and OBS preparation in chat and requested implementation. No repeat approval gate is needed.

- Windows x64 per-user installation; preserve application user data and previous versions.
- Publish immutable release files under https://framewise-download-2026.obs.cn-east-3.myhuaweicloud.com/releases/.
- One small .NET Framework bootstrapper executable downloads a hash-pinned release manifest, components and a small Inno installation core. No Java/Python preinstallation is required. Windows 10/11 includes the required .NET Framework baseline.
- Release metadata is embedded/pinned by the bootstrapper; all downloads use HTTPS, allowed origin/path, exact lengths and SHA-256. No cloud account credential is embedded.
- Persist partial downloads per release; validate HTTP Range responses; tolerate servers returning 200 by restarting the affected partial file; bounded automatic retry. Pause/restart preserves bytes. Checksum failures restart that package.
- Component ZIP archives install directly through Inno 7 external archive extraction. No temporary second full uncompressed payload is needed. The installation core separately checks each archive hash.
- UI exposes installation folder, disk requirement, progress/speed, pause/resume, retry, explicit errors and completion. Uninstall remains standard Inno and preserves external user data.
- Do not upload release files, modify OBS ACL, install/uninstall the real application, interrupt running Framewise, or replace the currently used directory build.
- Tests: deterministic package/manifest validation, local HTTP failure/resume fixtures, compiler checks, archive closure/hash checks, and UI smoke. No paid models.
- Native package source is rebuilt at 0.3.1 in an isolated output directory; existing releases/latest.json is preserved.
