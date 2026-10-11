# 自动框选 Implementation Plan
Goal: four initial images and selective recursion produce previewable30s timeline.
Architecture: local browser JPEG capture; Java proxy; Python bounded vision detection; pure client scanner; existingregionnodes reused.
Spec: ../specs/2026-10-11-auto-region.md
- [x] Red/green pure scanner tests: fourpoints, stable, switches, unknown, budget/cancellation.
- [x] Python detectvalidation+provider tests; Java proxy/validationtests.
- [x] Workspace controls, cancel and candidatepreview/apply; localshortvideo browser QA.
- [x] Fullregression, review, localdeployment andhandoff. No unsolicitedcommit/push.
