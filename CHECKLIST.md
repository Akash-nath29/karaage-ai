# Implementation Checklist

Source of truth: `PRD.md`. Ambiguities, decisions and deviations: `docs/decisions.md`.

## Definition of Done

An item is ticked **only** when all of these hold. Otherwise it stays unticked, with a note.

1. **Backend:** router → service → repository. Authorization is enforced server-side. No LLM calls in route handlers.
2. **Migration:** `alembic upgrade head` from an empty database succeeds.
3. **Test:** automated coverage of the happy path, plus an authorization-denied case for protected resources. The test file is named next to the item.
4. **Integrated:** the frontend uses the real API with no mock data, or the item is marked *API-only* with a reason.
5. **Verified:** exercised once end-to-end in the running app (`docker compose up`).

Format: `- [x] item — test: path/to/test`

---

## Phase 0: Decisions
- [x] PRD review: ambiguities, risks, missing details (`docs/decisions.md`)
- [x] Q1–Q4 answered (provider, parsing, batch trigger, search)
- [x] Q5 lesson schema shape: sections with roles + typed blocks (approved 2026-11-06)
- [x] Q6 production domain: none needed. Frontend and API share one Vercel project (2026-11-06, D37)
- [ ] Benchmark course materials provided (M14, before end of Phase 2)

## Phase 1: Foundation (single-user, D5)
**Exit:** in the running app, you can create a workspace, then create a course inside it. Backend and E2E tests pass.

Git is handled by the user (project `CLAUDE.md`: no git write operations).

✅ **Phase 1 complete (2026-11-05).** 6 API tests + 2 E2E tests passing against real Postgres.

- [x] `.gitignore`, `.env.example`, README run instructions
- [x] docker-compose: Postgres 17 + pgvector 0.8.7, bound to 127.0.0.1 — `infrastructure/docker-compose.yml`
- [x] Backend skeleton: FastAPI `/api/v1`, settings from env, logging, `/health` — test: `backend/tests/test_workspaces_courses.py::test_health`
- [x] DB: SQLAlchemy 2 base and session, Alembic, initial migration — test: `backend/tests/conftest.py` migrates an empty DB every run
- [x] Workspaces: create, list, get, patch, delete — test: `test_workspace_crud`, `test_workspace_validation_and_404`, E2E
- [x] Courses: create, list, get, patch, delete (cascade with workspace) — test: `test_course_crud`, `test_course_requires_existing_workspace`, `test_courses_scoped_to_workspace_and_cascade`, E2E
- [x] Frontend: Vite 8, React 19, TS 7, Tailwind 4, shadcn/ui, React Router 7, TanStack Query, API client — `npm run build` clean
- [x] Frontend: dashboard (workspaces), workspace screen (courses), course screen (details, edit, delete) — test: `frontend/e2e/workspace-course.spec.ts`
- [x] Tests: API against real Postgres — `backend/tests/`
- [x] Tests: E2E create → edit → reload → delete, plus fast not-found — `frontend/e2e/workspace-course.spec.ts`

Known: one oxlint warning in shadcn-generated `components/ui/button.tsx` (left as generated).

## Phase 2: Documents and Knowledge Engine
**Exit:** Workflow 2 passes. Recall@K and MRR are measured on the benchmark.

✅ **Phase 2 complete (2026-11-05).** 33 backend tests (in the worker image, OCR included; 32 + 1 skipped natively), 3 E2E tests, retrieval benchmark run with real Gemini embeddings.

- [x] Object storage: MinIO (Chainguard image, R14), private bucket, 5-minute signed URLs — test: `test_open_file_and_delete`. Avatar upload deferred with users (D5).
- [x] Celery + Redis worker (Docker, Tesseract inside), `jobs`/`job_events`, SSE stream with `Last-Event-ID` replay — test: `test_job_events_stream_and_replay`, E2E `documents.spec.ts`
- [x] Upload: content sniffing, 100 MB limit, zip-bomb guard, per-workspace checksum dedupe, kind (A9), course assignment, multi-file — test: `test_upload_validation`, `test_sniff_by_content_not_extension`, E2E
- [x] Extraction: PDF (PyMuPDF, headings by font size/bold, running headers removed, table rows rebuilt), scans/images (Tesseract OCR), DOCX, PPTX (slides + notes), TXT, MD — test: `tests/test_extraction_chunking.py` (`test_image_ocr` runs in the worker image)
- [x] Structure-aware chunking: heading path, page range, table content type, 800 max / 300 min / 100 overlap (configurable) — test: `test_chunks_*`, `test_tables_split_by_row_and_typed`
- [x] Provider abstraction for embeddings: Gemini + OpenAI-compatible (covers local servers, D6), retries honour the server's retry delay, token-capped batches — test: `tests/test_providers.py`. Chat and structured output move to Phase 3, where they're first used.
- [x] `llm_usage` recorded for every embedding call (D4) — test: `test_upload_ingest_search_cite`
- [x] Embeddings: `gemini-embedding-001`, 1536-dim, cached by embedded-text hash + model — test: `test_reprocess_reuses_embeddings`
- [x] Hybrid retrieval: HNSW (iterative scan) + OR-keyword FTS + workspace/course filter + weighted RRF + dedupe. No reranker (D9, measured) — test: `test_workspace_isolation_in_retrieval`, `test_course_scope_and_reassignment`, `test_weighted_fusion`
- [x] Citations: filename, page range, heading path; opens the source at `#page=N` via a signed URL (D7) — test: `test_open_file_and_delete`, E2E
- [x] Delete removes chunks from retrieval and the stored file. Reprocess. Transient provider failures retry (1/2/4 min), then fail with a message — test: `test_open_file_and_delete`, `test_transient_provider_outage_retries_then_fails`, `test_failed_extraction_is_reported`, `test_queue_unavailable_marks_failed`
- [x] Frontend: upload with live SSE progress, document list/status/errors, course assignment, reprocess, delete, search with citations (workspace and course pages) — test: `frontend/e2e/documents.spec.ts` (real worker + Gemini)
- [x] Benchmark: `python -m scripts.eval_retrieval` → hybrid Hit@1 0.82, Recall@5 0.96, Recall@10 0.96, MRR@10 0.884 (28 questions, `tests/benchmark/aiml_r23.json`)

Known:
- The benchmark questions were drafted by Claude and need a human review pass. Textbook and previous-year-paper material is still missing (M14).
- One benchmark question fails in every mode ("textbooks for Programming for Problem Solving"): the chunk on page 12 never names its course. Fixed by Phase 3's course/topic context on chunks.
- PDF table detection (`find_tables`) takes ~0.3 s/page: 70 s for the 215-page syllabus, in the background.
- Free-tier Gemini (30k embedding tokens/min) paces big documents to about 40 passages a minute: ~4.5 min for the syllabus.

## Phase 3: Syllabus and Research
**Exit:** Workflow 3 passes. Research returns cited, quality-scored sources for a topic.

✅ **Phase 3 complete (2026-11-06).** 74 backend tests (worker image), 4 E2E tests, live syllabus benchmark 4/4 courses, live research run.

- [x] Provider chat + structured output: Gemini and OpenAI-compatible, Pydantic validation with one repair attempt, usage and provenance recorded, model fallback list (D11) — test: `tests/test_research.py::test_structured_output_repairs_once_then_fails`, `tests/test_providers.py::test_chat_falls_back_to_the_next_model`
- [x] Syllabus upload + LLM extraction → draft (A10). Long documents are located first via a page outline; versioned prompts — test: `tests/test_syllabus.py` (short doc, long doc located, course not found, prompt fencing). Live: `python -m scripts.eval_syllabus` found the right pages and 100% of unit titles for 4/4 courses in the 215-page curriculum (`tests/benchmark/aiml_r23_syllabus.json`)
- [x] Chunk → topic mapping (D12): `document_chunks.topic_id`, automatic on confirm / edit / ingestion / course change, syllabus excluded, threshold 0.6 with evidence — test: `test_materials_map_to_topics`, `test_new_upload_maps_into_confirmed_course`. Manual per-document overrides moved to Phase 4. Chunk context headers not done (D13).
- [x] Syllabus review UI: unit/topic/subtopic add, rename, delete, reorder (ids survive renames and re-confirms), confirm; manual structure without a syllabus — test: `test_edit_draft_confirm_and_reparse_keeps_topic_ids`, `test_structure_edit_rename_reorder_delete`, E2E `syllabus-research.spec.ts`
- [x] Topic content status (A1) and unit/course coverage — test: `test_materials_map_to_topics`; topic page with mapped material
- [x] Research: sufficiency/gaps via the planning call (A20), focused queries, Tavily, no server-side fetching (D10), URL safety (R11), passage selection — test: `test_research_pipeline`, `test_unsafe_urls_rejected` (20 cases), `test_select_passages_prefers_topic_terms`, `test_upload_sites_and_navigation_text_are_not_evidence`
- [x] Research: quality tiers (M16), URL + content dedupe, per-domain cap, claim cross-check (M15), budget (≤ 4 searches, ≤ 8 sources, 2 LLM calls) — test: `test_research_pipeline`, `test_claim_statuses`, `test_quality_tiers`
- [x] `research_jobs`/`research_sources` + API (`POST/GET /topics/{id}/research`, `GET /research/{id}`, `/sources`, `/refresh`), 7-day reuse (§12.2), web vs uploaded-material citations kept apart — test: `test_research_reuse_refresh_and_latest`, `test_syllabus_is_not_material_for_research`, `test_search_failure_is_reported`, E2E
- [x] Stalled jobs restartable (M17) — test: `test_stalled_job_can_be_restarted`

Known:
- The syllabus and retrieval benchmarks were drafted by Claude and need a human review pass.
- Topic grouping from the LLM is sometimes coarse (e.g. ML "Ensemble Classification" as its own small topic). The review editor is where that gets fixed.
- Gemini free-tier flash models are often overloaded or rate-limited (R19). Fallbacks keep jobs working, but runs vary between ~30 s and several minutes.

## Phase 4: Content Generation
**Exit:** Workflow 4 passes, from topic selection through the rendered lesson with citations.

✅ **Phase 4 complete (2026-11-06).** 86 backend tests (worker image, OCR + KaTeX included), 5 E2E tests, live lesson generated and inspected in the browser.

- [x] Lesson schema 1.0 (Q5): sections with F3 roles × 14 typed F5 blocks, required sections per depth, versioned prompts (`lesson-v1`) — test: `test_document_conversion_drops_invalid_and_reports`
- [x] Pipeline (Workflow 4): pinned docs → mapped passages → retrieval → research only if materials fall short (E1) → generate (smart tier) → validate + one repair → math check → cite → save — test: `test_generate_lesson_with_citations`, `test_missing_sections_get_one_repair`
- [x] Diagrams compiled from structured nodes/edges (D15), 6 kinds, escaped labels — test: `test_diagrams_compile_and_escape`; live Mermaid render in the browser, no errors
- [x] Formula validation with real KaTeX, one repair, fallback to source (D16); Node + KaTeX in the worker image — test: `test_katex_validation_and_fallback`, `test_generate_lesson_with_citations`
- [x] Citations (M9/M18): label resolution, inline labels absorbed, quote snapshots survive deletion; material vs web vs AI-written shown per block (§11.2) — test: `test_inline_labels_move_into_citations`, `test_outdated_when_sources_change`
- [x] Versioning (F7): immutable versions with model, prompt version, source snapshot, tokens, warnings; older versions readable — test: `test_versions_enrich_and_feedback`, E2E
- [x] On-demand enrichment (F1 mode 2): one new section as a new version, no label collisions — test: `test_versions_enrich_and_feedback`, E2E
- [x] Outdated flag on document delete / reprocess / new material for the topic — test: `test_outdated_when_sources_change`
- [x] Feedback — test: `test_versions_enrich_and_feedback`, E2E
- [x] Manual document → topic pins feeding lesson evidence (D12) — test: `test_budget_and_pins`
- [x] Batch generation on syllabus confirm (Q3) with estimate (D20), cancel, "generate missing" — test: `test_confirm_queues_batch_and_cancel`, `test_estimate_shown_for_draft`, E2E
- [x] Workspace monthly budget (A18/D21) — test: `test_budget_and_pins`
- [x] Frontend: learning page (Screen 4) with one component per block type, Mermaid (strict, lazy-loaded), KaTeX, section index, sources, version history, regenerate, "ask for more", feedback; lessons and pins on the topic page; lesson status, batch progress and cancel on the course page — test: `frontend/e2e/lessons.spec.ts`
- Publish and private lessons came with multi-user (D28). Fork-by-copy wasn't built (viewers generate their own private version). Image block waits for image extraction (D18).

Known:
- Free-tier Gemini: pro models unavailable and flash capped at 20 requests/day, so lessons often come from flash-lite and are thinner (R21).
- One lesson E2E run stalled at "Waiting for a worker…" although the job had finished. Not reproduced in an isolated browser repro or in 4 later runs; watch for it.

## Phase 5: AI Tutor and Assessments
**Exit:** Workflows 5 and 6 pass. (Workflow 7 step 6, privacy between users, moves to Multi-user: there's one user, D5.)

✅ **Phase 5 complete (2026-11-06).** 95 backend tests (worker image), 6 E2E tests on the real stack with Gemini, question-extraction benchmark 31/31.

- [x] Tutor sessions: create (context from course, topic or lesson), list, continue, delete, message history — test: `test_sessions_context_and_crud`
- [x] Streaming answers over SSE with status, citations ([M1]/[W1] → sources with quotes), follow-up suggestions, errors and partial answers kept — test: `test_streamed_answer_with_citations_and_follow_ups`, `test_web_search_errors_budget_and_interruption`, `test_stream_falls_back_and_reports_usage`; E2E `tutor-assessment.spec.ts`
- [x] Modes: learn, doubt, Socratic, exam (A16 word targets), revision; optional web search per question (M19) — test: `test_streamed_answer_with_citations_and_follow_ups` (mode switch), `test_web_search_errors_budget_and_interruption` (exam + web)
- [x] Question extraction from papers, automatic after upload, topic mapping (D22), review UI (edit, key, approve, delete) (H3, M20) — test: `test_paper_extraction_and_review`; benchmark `scripts/eval_questions.py` on the synthetic paper; E2E
- [x] Quiz generation for a topic, unit, chosen topics or course with difficulty/marks/type filters (H4, A21), bank first then generated (M21) — test: `test_quiz_attempt_grading_and_progress`, `test_quiz_scopes_failures_and_regrade`
- [x] Marking: deterministic objective answers, rubric-based AI marking at temperature 0 with estimates labelled (H5, R16), "Grade again" — test: `test_grading_rules`, `test_quiz_attempt_grading_and_progress`, `test_quiz_scopes_failures_and_regrade`
- [x] Topic progress (A14, M22): mark studied, quiz updates, completed/revise states, weak and strong topics, revise-by — test: `test_progress_states`, `test_quiz_attempt_grading_and_progress`
- [x] Frontend: tutor screen (Screen 5) + tutor panel on lessons, quiz (Screen 6), results, question bank, progress dashboard (Screen 7), practice on course and topic pages — test: E2E `tutor-assessment.spec.ts`, `lessons.spec.ts` (panel)
- Privacy of sessions and progress between users and `GET /users/me/learning-analytics` came with Multi-user and Phase 6 below.

Known:
- The question benchmark is synthetic and clean (R25); real scanned papers are untested.
- Deleting a question removes it from past attempts too (no snapshot of the question in the attempt). Fine while a question bank is small and personal; snapshot it if results history matters.
- Re-extracting a paper replaces drafts you edited but didn't approve.

## Multi-user (D5 ended)
**Exit:** Workflows 1 and 7 pass.

✅ **Multi-user complete (2026-11-06).** 108 backend tests (worker image), 7 E2E tests including Workflows 1 and 7 with two browsers and email through Mailpit.

- [x] Auth: register, login, refresh rotation with reuse detection, logout, password hashing (stdlib scrypt, D26), rate limiting, CSRF guard (D25) — test: `tests/test_auth.py::test_register_login_refresh_logout`, `test_tokens_csrf_and_password_hashing`, `test_login_rate_limit`; E2E `multi-user.spec.ts`
- [x] Auth: email verification, forgot/reset password (Mailpit in development, D34) — test: `test_email_verification_and_password_reset`; E2E (confirmation link read from Mailpit)
- [x] Users: `GET/PATCH /users/me` (language, level, preferences feed the tutor), avatar, delete account (§10.5) — test: `test_profile_and_avatar`, `test_delete_account`
- [x] Members: list, change role, remove, leave (A11). Invitations (A12): email (bound to a verified address) and links, expiry, max uses, revoke — test: `tests/test_access.py::test_roles_members_and_invitations`; E2E
- [x] RBAC in `core/permissions.py` (every route declares a role; the resource in the path decides the workspace), RLS (R9, D27), audit log — test: `test_every_route_needs_sign_in` (all 80+ routes), `test_row_level_security`, `test_roles_members_and_invitations`
- [x] `user_id` on personal tables (tutor sessions, quizzes and attempts, topic progress, lesson feedback), lesson visibility and publish (A3, D28) — test: `test_lesson_visibility`, `test_workflow_7_tenant_isolation`
- [x] Tests: privacy of tutor sessions and progress between users (Workflow 7 step 6) — test: `test_workflow_7_tenant_isolation`; E2E
- [x] Existing data handed to a real account (D29) — test: `test_claim_existing_data`
- [x] Frontend: sign-in, register, verify, forgot/reset, invitation, profile; members, invitations and activity; controls shown by role (the server enforces them) — test: E2E `multi-user.spec.ts`
- [x] Tests: authorization, tenant isolation, E2E Workflows 1 and 7 — `tests/test_access.py`, `e2e/multi-user.spec.ts`

Known:
- No Google sign-in (optional, D35). Emails go out synchronously after the commit (D34); a failed send is logged and can be resent.
- Access tokens can't be revoked before they expire (15 minutes); signing out and password resets end the refresh sessions at once.
- Rate limits (Redis, fail open if Redis is down): 10 sign-in attempts per email per 15 minutes; per IP 300 sign-ins per 5 minutes and 100 registrations per hour, because a campus network puts a whole class behind one IP; 3 reset emails per address per hour; 50 invitations per person per hour.
- RLS covers workspace content and personal data; `workspaces`/`workspace_members` and private-lesson visibility are checked in code only (D27).

## Phase 6: Productization
**Exit:** all 7 acceptance workflows pass against a deployed environment. The deployment config is ready (D37) but nothing is deployed yet. The rest is done, and the 7 workflows pass on the local stack.

- [x] Personal dashboard + learning analytics (§I, Screen 1, `GET /users/me/learning-analytics`, D31) — test: `test_learning_analytics_and_usage`; E2E (dashboard after sign-up)
- [x] Shared learning resources: the workspace's lessons (shared + your private ones) — test: `test_lesson_visibility`
- [x] Usage dashboard and limits: per workspace (per member for admins), per person, `USER_MONTHLY_TOKENS` (§12.6, D30) — test: `test_learning_analytics_and_usage`
- [x] Rate-limit review (sign-in, registration, password reset, verification, invitations) and security testing (route sweep, tenant isolation, RLS, CSRF, token tampering, viewers can't read answer keys) — test: `test_access.py`, `test_auth.py`
- [ ] Sentry, backups: built (`SENTRY_DSN`, Neon point-in-time restore, D33). Tick once an error from the deployed app reaches Sentry.
- [ ] Deployment (Vercel frontend + API, Render worker + Redis, Neon, Supabase Storage; D37): `vercel.json`, `api/index.py`, `render.yaml`, README "Deploy". Migrations checked as a non-superuser on fresh Postgres 17. Tick when the 7 acceptance workflows pass on the deployed app.
