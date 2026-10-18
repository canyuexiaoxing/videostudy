# YOLO-only occlusion grouping implementation plan

User approved implementation and testing in this chat. Execute inline in the existing checkout; preserve existing untracked experiments. Initially no commit/push/deployment; subsequent deployment and GitHub push were explicitly authorized in chat.

1. [x] Add failing tests for authenticated mask sidecars and actual selected-frame capture; implement person_visibility.py plus bounded transfer in frame_stream.py/visual_evidence.py. Verify off captures identical and inference count unchanged.
2. [x] Add failing grouping tests; implement person_grouping.py helpers and narrowly gated slide_grouping.py path. Protect evidence and pending streaming behavior.
3. [x] Thread enabled mode and sidecar fingerprints through legacy/direct/grouped checkpoints; keep off cache keys identical. Bump only enabled visual selection context.
4. [x] Run affected and full Python offline tests, independent code review, then existing-course quality/time evaluation in .local/qa. Correct earlier QA mask color-order mismatch if runtime comparison confirms it; do not reuse unauthenticated old masks as production evidence.
5. [x] Record actual output, remaining risks and report paths. Do not claim model quality or full-course mathematical completeness from local tests.

Ledger: initial tracked tree clean at 2cd0fec. Numerous prior untracked QA scripts/specs/videos are user-context artifacts and must remain untouched.

Final evidence: .local/qa/yolo-grouping-fix-20261018/测试结论.md; 511 tests (1 integration skip), 4-course off exact equivalence, enabled 109-frame replay 35→30 groups / 35→41 representatives; no deployment.

2026-10-18 follow-up: user explicitly requested deployment to running backend. Updated both official Dockerfiles to include new modules; preserved previous image tag before-yolo-grouping-20261018; rebuilt local image and recreated only agent-python with original GPU/per-video settings. Health healthy, 11 running modules SHA256 match workspace, 24 image-based regression tests pass, history API HTTP200. No history analysis automatically invoked. Evidence: .local/qa/yolo-grouping-fix-20261018/deployed-verification.json and deployed-tests.log.

2026-10-18 final follow-up: user requested pushing completed changes to GitHub. Include production code, regression tests, deployment support and this handoff. Exclude local videos, runtime data and unrelated untracked experiments. Final behavior and verification are summarized in docs/交接-2026-10-18.md.
