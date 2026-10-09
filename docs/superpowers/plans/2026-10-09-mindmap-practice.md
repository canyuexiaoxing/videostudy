# Mind-map practice implementation plan

**Goal:** Persist evidence-linked exercises and immediately grade an option click.
**Architecture:** Python generates and validates structured exercises; Java owns MySQL state and scoring; Vue displays only public questions and per-session feedback.
**Tech Stack:** FastAPI, DeepSeek fast mode, Spring/JdbcTemplate/Flyway, Vue/SVG.
**Spec:** ../specs/2026-10-09-mindmap-practice.md

## Constraints
No automatic generation, no subtitle changes, no arbitrary generated SVG, no extra semantic review request. Invalid questions are dropped. Snapshot evidence before async generation.

- [x] Write failing Python checks; implement evidence/schema/calculation/diagram validator and one-pass generation.
- [x] Add Flyway tables and Java store/controller; test grading, answer hiding, retries, foreign keys and cache reuse.
- [x] Add range/count/difficulty controls, diagram renderer and immediate-click feedback; retain static demo only when there is no course.
- [x] Build, run focused and regression tests; deploy local services and test one small DeepSeek exercise set end-to-end.
- [x] Record verification evidence and limitations in docs/AI练习验证.md.
