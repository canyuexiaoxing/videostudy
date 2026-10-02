# Grounded Mind Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Generate a real course mind map whose nodes seek to cited original media segments.

**Architecture:** Python creates bounded Agent summaries from transcript chunks and validates all cited IDs against the transcript. Java stores the optional tree inside the existing analysis result JSON. Vue renders the tree and uses the local media player's seek path plus transcript highlighting.

**Tech Stack:** Python 3.11, FastAPI, DeepSeek Chat API, Java 21/Spring Boot/Jackson, Vue 3/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-28-grounded-mind-map-design.md`

## Global Constraints

- All times are integer milliseconds and are derived from existing transcript segments.
- Do not store or require the source video after successful analysis.
- Legacy results without `mindMap` must continue to load.
- Only cited, existing segment IDs may become knowledge nodes.

## Review Focus

- The model invents an ID or time: discard that claim and derive valid times locally.
- Audio-only media has transcript but no page groups: still generate the map.
- Empty transcript: return explicit empty status.
- A chunk request fails: retain validated nodes, mark map failed, preserve analysis result.
- The user reads a result without selecting its local file: show evidence and a reselect prompt.

---

### Task 1: Python evidence-bound map generation

**Files:** Create `agent-python/mind_map.py`, `agent-python/test_mind_map.py`; modify `agent-python/analysis.py`, `agent-python/test_analysis.py`.

**Interfaces:** `build_mind_map(segments, page_groups, ask_json=None) -> dict`; output matches spec's `mindMap` object.

- [x] Write tests for valid citations, invalid citations, empty audio, chunking and failed model calls.
- [x] Run tests and confirm they fail due to missing generator.
- [x] Implement chunk prompts, strict model JSON validation and evidence-derived times.
- [x] Connect generator after page analysis and test the full result shape.

### Task 2: Java result compatibility

**Files:** Modify `backend-java/src/main/java/cn/videostudy/api/TranscriptionController.java`; add contract assertions to `backend-java/src/test/java/cn/videostudy/api/PageGroupResultTest.java`.

**Interfaces:** Optional recursive `MindMapNode`, `MindMapEvidence`, `MindMapResult` records in `TranscriptResult`.

- [x] Test new map deserialization and old result without map.
- [x] Add records and overload prior constructors without breaking existing tests.
- [x] Run backend tests.

### Task 3: Vue tree and source seek

**Files:** Modify `desktop/src/App.vue`, `desktop/src/style.css`; create `desktop/src/MindMapNode.vue` and `desktop/src/mindMap.ts`.

**Interfaces:** TypeScript map types and `seekTo(startMs, sourceId?)`; recursive node emits selected node.

- [x] Add a focused tree/source behavior test where feasible; keep player seeking centralized.
- [x] Render an accessible three-level tree and source quote panel.
- [x] Highlight and scroll cited transcript; handle missing local media.
- [x] Build Vue; preview is available at http://127.0.0.1:5173/.
- [x] Visually inspect the layout in a browser and verify a node seeks the local 30-minute video.

### Task 4: Integration and documentation

**Files:** Update `README.md` with feature status and limits.

- [x] Run focused Python tests, Java tests, Vue build and `git diff --check`.
- [x] Verify no example/demo node is presented as genuine Agent output.
- [x] Report whether a real-video/API end-to-end run was performed.

### Task 5: Generate maps for completed legacy jobs

**Files:** Modify `agent-python/app.py`, `backend-java/src/main/java/cn/videostudy/api/MediaAnalyzer.java`, `HttpMediaAnalyzer.java`, `TranscriptionJobStore.java`, `TranscriptionController.java`, `desktop/src/App.vue`; create `backend-java/src/main/java/cn/videostudy/api/MindMapController.java` and tests.

**Interfaces:** `POST /api/transcriptions/{id}/mind-map` returns `MindMapResult`; internal Python `POST /mind-map` consumes persisted transcript/page data.

- [x] Test missing, incomplete and existing completed jobs; test Python request route.
- [x] Implement internal generator call and atomic replacement of only `mindMap` in result JSON.
- [x] Add frontend button for old and partly failed tasks; disable during generation.
- [x] Verify existing 30-minute saved task can generate a map without re-upload.
