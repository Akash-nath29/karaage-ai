# SemSaviour: Personal AI Tutor

Turns your syllabus, textbooks and notes into structured lessons, a tutor and practice quizzes. Spec: `PRD.md`. Progress: `CHECKLIST.md`. Decisions and deviations: `docs/decisions.md`.

> **Multi-user, local development.** Accounts, workspace roles and invitations work; deployment (domain, HTTPS, Sentry) isn't set up yet (decisions D33, Q6). Keep it on localhost until then.

## Prerequisites

Docker Desktop (running), Python 3.11+, Node 22+, [uv](https://docs.astral.sh/uv/), a Gemini API key and a Tavily API key.

## Run

```sh
cp .env.example .env               # then set GEMINI_API_KEY, TAVILY_API_KEY and SECRET_KEY (see the comment there)

# 1. Postgres + pgvector, Redis, MinIO (object storage), Mailpit (email) and the worker; all bound to 127.0.0.1
docker compose -f infrastructure/docker-compose.yml up -d --build --wait

# 2. Backend at http://127.0.0.1:8000 (API docs at /docs)
uv venv .venv                      # skip if .venv exists
uv pip install --python .venv -r backend/requirements.txt
npm install --prefix backend/tools  # KaTeX, for formula checks when the backend runs outside Docker
cd backend
../.venv/Scripts/python -m alembic upgrade head   # macOS/Linux: ../.venv/bin/python
../.venv/Scripts/python -m uvicorn app.main:app --reload

# 3. Frontend at http://127.0.0.1:5173 (proxies /api to the backend)
cd frontend
npm install
npm run dev
```

**Accounts.** Open http://127.0.0.1:5173 and create an account. Emails (confirmation, password reset, invitations) land in Mailpit at http://127.0.0.1:8025 during development. Data from before accounts existed belongs to a placeholder until you claim it once, after registering:

```sh
cd backend && ../.venv/Scripts/python -m scripts.claim_data you@example.com
```

**Workspaces and roles** (PRD §4.2, decision A11). Whoever creates a workspace owns it. Invite people from the workspace page by email or with a link, as:
- **viewer:** reads shared material, uses the tutor, takes quizzes, generates private lessons;
- **editor:** also uploads documents, generates and shares lessons, and edits the question bank;
- **admin:** also manages courses, the syllabus and members (not other admins);
- **owner:** everything, including admins and deleting the workspace.

Tutor conversations, quizzes, progress and private lessons are personal: nobody else sees them, the owner included. The dashboard shows your progress across every workspace; each workspace shows its lessons, members, recent activity (admins) and AI usage against the monthly budget. Your profile shows your own usage, and lets you set the tutor's language or delete your account.

On a course page:
1. **Study materials:** upload notes, textbooks and your syllabus (type: Syllabus). The worker extracts text (OCR for scans and images), chunks it and embeds it, with live progress. A whole-programme curriculum PDF works too.
2. **Syllabus:** pick the syllabus document and parse it. The course is found by title and code, even in a 200-page curriculum. Review the draft units and topics, fix them, then confirm. Materials get matched to topics automatically.
3. **Lessons:** confirming the syllabus starts writing a lesson for every topic in the background (cancellable). Each lesson has sections, diagrams, formulas, worked examples, a quiz and flashcards, and every block shows whether it came from your materials, the web, or the AI. You can generate other depths, regenerate (a new version, old ones stay readable), or ask for more (adds a section).
4. **Topics:** each topic page shows its lessons, the matching passages from your materials, and pinned documents. **Research this topic** checks the gaps, searches the web (Tavily), and cross-checks key facts.
5. **AI tutor:** "Ask the tutor" on a course, topic or lesson. Answers stream in, cite your materials (and the web when you tick it), and suggest follow-ups. Modes: doubt, learn, Socratic, exam (2/5/10-mark answers), revision. Conversations are kept.
6. **Question papers:** upload previous-year or suggestion papers to the course with the type "Question paper". Their questions are extracted, matched to topics and put in the **question bank** as drafts to review and approve.
7. **Quizzes:** "Quiz me" on a topic, or a course/unit quiz with difficulty, marks and type filters. Objective answers are marked instantly, written answers by the AI against a rubric (an estimate), with feedback and a reference answer.
8. **Progress:** mark topics studied; quizzes update accuracy, weak areas and what to revise.
9. **Search your materials:** each result links to its source page.

The worker mounts `backend/` but doesn't reload: after changing backend code, run `docker compose -f infrastructure/docker-compose.yml restart worker`. After editing `.env`, use `up -d --force-recreate worker` instead (`restart` keeps the old environment). MinIO's console is at http://127.0.0.1:9001 (user `semsaviour`, password `semsaviour-secret`).

## Test

```sh
cd backend && ../.venv/Scripts/python -m pytest       # API + pipeline tests: real Postgres/MinIO/Redis, fake AI
docker compose -f infrastructure/docker-compose.yml run --rm --no-deps worker python -m pytest -p no:cacheprovider  # same, plus OCR
cd frontend && npx playwright install chromium        # once
cd frontend && npm run test:e2e                       # browser E2E: needs the compose stack incl. worker, Mailpit + real keys
cd backend && ../.venv/Scripts/python -m scripts.eval_retrieval   # retrieval benchmark (Recall@K, MRR), real key
cd backend && ../.venv/Scripts/python -m scripts.eval_syllabus    # syllabus parser benchmark (4 courses), real key
cd backend && ../.venv/Scripts/python -m scripts.eval_questions   # question extraction on the SYNTHETIC OS paper, real key
```

## Database changes

Edit models in `backend/app/modules/<module>/models.py` (add new ones to `app/database/models.py`), then:

```sh
cd backend
../.venv/Scripts/python -m alembic revision --autogenerate -m "describe change"
../.venv/Scripts/python -m alembic upgrade head
```
