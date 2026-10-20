# Framewise Native Windows Implementation Plan

> For agentic workers: use executing-plans and parallel domain implementation. User explicitly authorizes autonomous execution without intermediate design approvals.

**Goal:** Deliver a Docker-free Windows local application with GPU-first hardware policy, safe local data, model preparation, installer and verifiable tests.
**Architecture:** Electron supervises bundled Java and isolated Python processes; renderer uses discovered loopback origin; SQLite and model assets live under userData. Native storage, Python devices and renderer UI are separate work units integrated by root.
**Tech Stack:** Electron38, Vue3, Java21/SpringSQLite, Python3.11+, PaddleOCR, faster-whisper, TorchYOLO, FFmpeg, Windows installer.
**Spec:** docs/superpowers/specs/2026-10-19-native-windows-design.md

## Constraints and review focus
- Preserve current course algorithms and existing user data.
- No raw secrets/model payload logging, no destructive filesystem traversal.
- Verify process ownership, model authenticity, and partial startup cleanup.
- GPU unavailable/OOM: module-specific behavior, strictGPU fails rather than silent CPU.
- Never claim clean-machine/multi-GPU compatibility without testing.

## Tasks
- [x] Native device bootstrap: explicit modes, minimal probes and DLL setup; failing tests then implementation; actual CPU/GPU smoke.
- [x] Local storage/model manager: encrypted secrets, resumable hashing downloads, backup/restore/diagnostics and cache safety; fault tests.
- [x] UI: runtime settings/onboarding and dynamic loopback origin; empty-practice retry UX and tests.
- [x] Runtime supervisor and Java auth: tokenized loopback processes, readiness/exit/crash/port collision handling; lifecycle tests.
- [x] Reproducible native runtime builder: official dependencies, pinned assets, integrity manifest, licenses, Python isolation and FFmpeg/Java bundle.
- [x] Installer/updater/uninstaller: per-user no-admin install, preserve data, integrity checking and rollback. Earlier rehearsal passed; further installer validation excluded by user. Final compressed artifact compilation tracked in delivery report.
- [x] Integrated full regression, native end-to-end real video and model API tests, data restore and crash recovery; defect fixes.
- [x] Final evidence report with wall-clock timings, stage durations, artifact paths and explicit remaining limits.
