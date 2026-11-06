# PRODUCT REQUIREMENTS DOCUMENT (PRD)
# Personal AI Tutor
**Product Version:** 1.0  
**Document Status:** Ready for Development  
**Product Type:** Cloud-based, multi-user AI learning platform  
**Primary Objective:** Build an intelligent learning environment that transforms user-provided academic materials and external knowledge into structured, interactive and visually engaging study experiences.

---

# 1. PRODUCT OVERVIEW

## 1.1 Product Description

Personal AI Tutor is a cloud-based AI-powered learning platform designed to help students understand academic subjects, prepare for examinations and organize their learning materials.

The platform combines Retrieval-Augmented Generation (RAG), web research, large language models and structured content generation to create personalized educational experiences.

Users can upload their academic materials, including:

- University syllabi
- Textbooks
- Lecture notes
- Previous-year question papers
- Suggestion questions
- PDF documents
- DOCX documents
- PowerPoint presentations
- Images and scanned notes
- Other supported academic resources

The system processes these materials, understands their academic structure and creates a searchable knowledge base.

When a student requests study material on a particular topic, the system follows an intelligent workflow:

1. Understand the student's request.
2. Identify the relevant syllabus topic.
3. Retrieve relevant information from uploaded documents.
4. Determine whether the retrieved information is sufficient.
5. Conduct web research to fill knowledge gaps.
6. Consolidate the available evidence.
7. Generate structured study material.
8. Create relevant diagrams, examples, tables and visual explanations.
9. Attach citations and source references.
10. Save the generated lesson for future revision.

The platform also includes an interactive AI tutor, assessment engine, personalized progress tracking and collaborative workspaces.

## 1.2 Product Vision

Build an AI learning environment that behaves like a combination of:

- A personal academic tutor.
- A research assistant.
- A structured digital textbook.
- An examination preparation assistant.
- A personalized learning management system.

The product must not behave like a conventional chatbot that simply returns long text responses.

Its primary output should be structured learning experiences that are easy to read, understand, navigate and revise.

## 1.3 Core Product Philosophy

**Knowledge first. Teaching second. Assessment third.**

The system must:

1. Understand what the student needs to learn.
2. Gather reliable and relevant information.
3. Explain that information in an understandable manner.
4. Test whether the student has understood it.
5. Identify knowledge gaps and recommend what to study next.

---

# 2. TARGET USERS

## 2.1 Primary Users

### University Students

Students studying undergraduate and postgraduate courses who need help with:

- Semester examinations.
- Understanding difficult concepts.
- Preparing answers according to marks.
- Organizing study materials.
- Practicing previous-year questions.
- Revising large syllabi.
- Identifying important topics.

### College Study Groups

Students who want to collaborate by sharing:

- Syllabi.
- Lecture notes.
- Reference materials.
- Generated study guides.
- Practice questions.
- Subject-specific knowledge bases.

## 2.2 Secondary Users

### Independent Learners

People learning subjects outside formal education.

### Educators

Teachers who want to upload learning materials and create reusable educational resources for students.

Educator-specific administration and classroom management are future extensions, not MVP requirements.

---

# 3. PRODUCT SCOPE

The product will consist of eight primary modules.

| Module | Description |
|---|---|
| Authentication | User registration, login and identity management |
| Workspace Management | Personal and collaborative learning environments |
| Academic Management | Courses, syllabi, units and topics |
| Knowledge Engine | Document ingestion, indexing and RAG |
| Research Engine | External web research and source verification |
| Content Generation | Structured lesson and study material generation |
| AI Tutor | Interactive, context-aware teaching assistant |
| Assessment Engine | Quizzes, answer evaluation and progress tracking |

---

# 4. USER ROLES AND PERMISSIONS

The platform must support multiple users from its initial release.

## 4.1 Workspace Model

A workspace is the primary container for academic resources.

A workspace may contain:

- Multiple courses.
- Multiple documents.
- Multiple students.
- Shared lessons.
- Shared questions.
- Research resources.
- Workspace-specific knowledge bases.

Every workspace must have an owner.

## 4.2 User Roles

### Owner
- Create and delete workspace.
- Upload and delete documents.
- Create courses.
- Manage workspace settings.
- Invite and remove members.
- Assign permissions.
- Generate and publish shared lessons.

### Admin
- Upload documents.
- Manage courses.
- Generate and edit lessons.
- Invite members.
- Manage most workspace resources.

### Editor
- Upload documents.
- Generate lessons.
- Edit permitted learning resources.
- Create assessments.

### Viewer
- View shared documents and lessons.
- Ask questions through the AI tutor.
- Generate private explanations.
- Take quizzes.
- Maintain personal progress.

Viewer-generated content must remain private unless explicitly published or shared.

## 4.3 Personal and Shared Data

The platform must distinguish between:

**Workspace data**
- Shared documents.
- Courses.
- Syllabi.
- Shared lessons.
- Publicly available questions.

**Personal data**
- Tutor conversations.
- Personal notes.
- Quiz attempts.
- Learning history.
- Individual progress.
- Personalized study plans.

One user must never be able to access another user's private data.

---

# 5. FUNCTIONAL REQUIREMENTS

# MODULE A: AUTHENTICATION AND USER MANAGEMENT

## A1. User Registration

Users must be able to register using:

- Email.
- Password.
- Display name.

Email verification should be supported.

Google OAuth can be implemented as an additional authentication option.

## A2. Login

Users must be able to log in securely.

Requirements:
- Secure password hashing.
- Access token management.
- Refresh token rotation.
- Logout.
- Session expiration.
- Password reset.

## A3. User Profile

Users should be able to manage:
- Display name.
- Profile picture.
- Preferred learning language.
- Academic level.
- Learning preferences.

---

# MODULE B: WORKSPACE MANAGEMENT

## B1. Workspace Creation

Users can create multiple workspaces.

Workspace fields:
- Workspace name.
- Description.
- Owner.
- Visibility.
- Creation timestamp.

## B2. Workspace Dashboard

Display:
- Courses.
- Uploaded documents.
- Recent activity.
- Members.
- Recently generated lessons.
- Learning progress.

## B3. Member Invitations

Workspace owners and authorized admins can invite other users.

Invitation methods:
- Email invitation.
- Invitation link.

Invitation links must support expiration and revocation.

## B4. Resource Sharing

Users should be able to control the visibility of generated learning material.

Visibility options:
- Private.
- Workspace shared.

Public sharing through externally accessible links can be introduced in a later release.

---

# MODULE C: ACADEMIC MANAGEMENT

## C1. Course Creation

Users can create courses within workspaces.

Course fields:
- Course title.
- Course code.
- Description.
- Academic year or semester.
- Workspace ID.
- Creator.

## C2. Syllabus Upload

Users can upload their syllabus as a document.

The system must extract:

- Subject name.
- Subject code.
- Units.
- Chapters.
- Topics.
- Subtopics.
- Available marks or examination structure.
- References, where available.

## C3. Syllabus Parsing

The system must use an LLM-assisted structured extraction pipeline.

The extracted syllabus should be represented as a hierarchy:

Course → Units → Topics → Subtopics.

Users must be able to review and manually edit the extracted structure.

The original uploaded syllabus must remain available.

## C4. Topic Management

Users must be able to:
- View topics by unit.
- Edit topic names.
- Add missing topics.
- Delete incorrect topics.
- Reorder topics.
- Map documents to topics.
- View lesson generation status.

## C5. Syllabus Coverage

Each topic should have a learning status:

- Not started.
- Materials available.
- Lesson generation pending.
- Lesson available.
- Studied.
- Revision required.
- Completed.

The platform must calculate topic and unit-level coverage.

---

# MODULE D: DOCUMENT MANAGEMENT AND RAG

This is one of the most critical components of the product.

## D1. Supported File Types

Initial support:

- PDF.
- DOCX.
- PPTX.
- TXT.
- Markdown.
- PNG.
- JPG/JPEG.

Scanned PDF and image OCR must be supported.

Handwriting recognition can be improved in a later release.

## D2. Document Upload

Users must be able to:
- Upload individual documents.
- Upload multiple documents.
- Assign documents to courses.
- Optionally associate documents with topics.
- View processing status.
- Delete documents.
- Reprocess documents.

The frontend must display ingestion progress.

## D3. Document Processing Pipeline

Implement the following pipeline:

1. Validate file type and size.
2. Calculate document checksum.
3. Store the original file in object storage.
4. Create a document record.
5. Add an ingestion job to the background queue.
6. Extract document content and structure.
7. Apply OCR when necessary.
8. Identify headings, paragraphs, tables and page boundaries.
9. Perform semantic or structure-aware chunking.
10. Generate embeddings.
11. Save chunks and metadata.
12. Mark ingestion as completed.

Document processing must be asynchronous.

A failed ingestion job must support retries.

## D4. Chunking

Use hierarchical, structure-aware chunking.

Initial recommended parameters:

- Target chunk size: 500–800 tokens.
- Overlap: 80–120 tokens.
- Preserve headings and section hierarchy.
- Preserve table structures.
- Preserve page references.
- Avoid splitting equations or examples unnecessarily.

These parameters must be configurable.

## D5. Chunk Metadata

Each chunk should retain:

- Chunk ID.
- Document ID.
- Workspace ID.
- Course ID.
- Topic ID, where known.
- Parent chunk or section reference.
- Chapter.
- Section.
- Page number or page range.
- Content type.
- Original content.
- Embedding model identifier.
- Creation timestamp.

## D6. Retrieval Architecture

Implement hybrid retrieval consisting of:

1. Semantic vector search.
2. Keyword retrieval using BM25 or PostgreSQL full-text search.
3. Metadata filtering.
4. Result deduplication.
5. Reranking.
6. Context assembly.

The retrieval system must respect workspace permissions.

Initial retrieval configuration:

- Retrieve approximately 30 candidates.
- Rerank the candidates.
- Return approximately 6–10 relevant passages.
- Adjust context length based on the selected LLM.

These values must be configurable and evaluated against real documents.

## D7. Source Attribution

Every retrieved passage must preserve its original source.

Generated material should identify:
- Source document.
- Page number.
- Section or chapter.
- Relevant citation.

Users should be able to navigate from a citation to the original source.

---

# MODULE E: WEB RESEARCH ENGINE

The platform must not depend exclusively on uploaded documents.

External research is required to fill missing information.

## E1. Research Trigger

Web research should happen when:

- Relevant information is missing from the knowledge base.
- Retrieved information is insufficient.
- The student explicitly requests additional research.
- The system needs additional examples or explanations.
- Important factual claims require verification.

Research must not automatically happen for every user request.

## E2. Research Workflow

1. Understand the requested topic.
2. Retrieve existing academic material.
3. Evaluate evidence sufficiency.
4. Identify missing concepts.
5. Generate focused search queries.
6. Search the web.
7. Extract relevant page content.
8. Evaluate source quality.
9. Deduplicate sources.
10. Cross-check important claims.
11. Construct structured evidence.
12. Return evidence to the content generation engine.

## E3. Source Quality

Prefer:

- University websites.
- Academic textbooks and educational resources.
- Research publications.
- Official documentation.
- Reputable educational platforms.
- Established technical publications.

Low-quality or unverifiable sources should not be treated as authoritative.

## E4. Research Budget

Implement configurable limits.

Initial suggested defaults:

- 3–5 search queries per topic.
- 5–10 useful source pages.
- Bounded extracted content.
- Limited verification calls.

Avoid unlimited research loops.

## E5. Research Citations

Store:
- Source title.
- URL.
- Domain.
- Publication date, when available.
- Retrieval timestamp.
- Extracted relevant passages.
- Associated topic.
- Source type.
- Verification status.

Generated content must distinguish uploaded-document citations from web citations.

## E6. Research Safety

Retrieved websites must be treated as untrusted content.

The system must:
- Ignore instructions embedded in external pages.
- Prevent prompt injection.
- Restrict extraction to safe public URLs.
- Block localhost, private IP addresses and cloud metadata endpoints.
- Avoid arbitrary URL fetching without validation.

---

# MODULE F: CONTENT GENERATION ENGINE

This module transforms retrieved evidence into educational content.

## F1. Generation Modes

The platform must support two generation modes.

### Mode 1: Batch Generation

When a syllabus is processed, the system creates generation jobs for its topics.

Each topic can be independently:
- Retrieved.
- Researched.
- Generated.
- Validated.
- Saved.
- Retried.

Batch generation must happen asynchronously.

### Mode 2: On-demand Generation

When a student opens a topic or requests additional information:

1. Retrieve the existing lesson.
2. Retrieve relevant academic evidence.
3. Determine whether the lesson needs enrichment.
4. Conduct additional research if necessary.
5. Generate a targeted explanation or lesson extension.
6. Save the resulting content.

Do not regenerate an entire lesson when a small explanation is sufficient.

## F2. Generation Depth

Support the following content depths:

- Beginner-friendly.
- Conceptual understanding.
- Detailed academic explanation.
- Exam-oriented.
- Quick revision.
- Advanced exploration.

## F3. Study Material Structure

Every generated lesson should support:

### 1. Introduction
- Topic overview.
- Why the topic matters.
- Estimated learning time.

### 2. Learning Objectives
What the student should understand after completing the lesson.

### 3. Prerequisites
Concepts the student should understand beforehand.

### 4. Concept Explanation
Clear explanations with progressive difficulty.

### 5. Visual Learning
Relevant diagrams, flowcharts, illustrations and concept maps.

### 6. Examples
Practical examples and worked solutions.

### 7. Important Definitions
Exam-relevant terminology.

### 8. Comparison
Comparison tables for related concepts.

### 9. Common Mistakes
Frequently misunderstood concepts.

### 10. Examination Preparation
Potential question formats and model answer structures.

### 11. Quick Revision
Concise revision notes.

### 12. Practice Questions
Questions that evaluate understanding.

## F4. Structured Learning Document

The backend must generate a validated JSON learning document.

Example:

{
  "schema_version": "1.0",
  "title": "Database Normalization",
  "topic_id": "uuid",
  "estimated_minutes": 25,
  "learning_objectives": [],
  "sections": [
    {
      "id": "section-1",
      "type": "concept",
      "title": "Introduction",
      "content": {
        "markdown": "..."
      },
      "citations": []
    },
    {
      "id": "section-2",
      "type": "diagram",
      "title": "Normalization Process",
      "content": {
        "renderer": "mermaid",
        "source": "flowchart TD..."
      },
      "citations": []
    },
    {
      "id": "section-3",
      "type": "example",
      "title": "Practical Example",
      "content": {
        "markdown": "..."
      },
      "citations": []
    }
  ]
}

The schema must be versioned and validated using Pydantic.

## F5. Supported Content Blocks

Initial supported blocks:

- Concept.
- Heading.
- Paragraph.
- Diagram.
- Table.
- Comparison.
- Formula.
- Code.
- Example.
- Callout.
- Step-by-step explanation.
- Quiz.
- Flashcards.
- Summary.
- Image.

The frontend must render each content block using a dedicated component.

Never execute arbitrary HTML or JavaScript generated by an LLM.

## F6. Diagram Generation

Support:

- Mermaid flowcharts.
- Sequence diagrams.
- Entity relationship diagrams.
- Class diagrams.
- State diagrams.
- Concept maps.
- Mathematical formulas using KaTeX.

The diagram generation process:

1. Generate diagram source.
2. Validate syntax.
3. Render the diagram.
4. Detect rendering failures.
5. Retry generation when necessary.
6. Save valid diagram source with the lesson.

Technical diagrams should be rendered programmatically rather than relying on image generation.

## F7. Lesson Versioning

Every generated lesson must have:
- Lesson ID.
- Version number.
- Generation timestamp.
- Model identifier.
- Prompt version.
- Source snapshot.
- Generation metadata.

A lesson should not be silently overwritten.

Changes in underlying documents should flag potentially outdated lessons.

---

# MODULE G: AI TUTOR

The AI tutor provides an interactive learning experience.

It must be aware of:

- Current workspace.
- Current course.
- Current topic.
- Existing lesson.
- Uploaded documents.
- Relevant research sources.
- Previous conversation context.

## G1. Learning Modes

### Learn Mode

The tutor explains topics progressively.

It should:
- Break complex concepts into smaller sections.
- Use examples and analogies.
- Check student understanding.
- Adjust explanation depth.
- Avoid unnecessarily long answers.

### Doubt Mode

Students can ask questions about any academic concept.

Answers should prioritize relevant uploaded materials and use web research when necessary.

Citations should be provided.

### Socratic Mode

The tutor should guide the student toward the answer through questions instead of immediately revealing the solution.

### Exam Mode

The tutor helps students prepare exam-oriented answers.

Support:
- 2-mark answers.
- 5-mark answers.
- 10-mark answers.
- Long-form questions.
- Numerical problems.
- Previous-year questions.

Answers should match the requested depth and academic level.

### Revision Mode

The tutor creates:
- Concise notes.
- Important definitions.
- Flashcards.
- Key formulas.
- Quick summaries.
- Topic revision questions.

## G2. Conversation Management

Users should be able to:
- Create tutor sessions.
- Continue previous sessions.
- Delete sessions.
- View message history.
- Reference a particular topic.
- Ask follow-up questions.

Conversation history must be private to the individual user.

## G3. Streaming

Tutor responses should stream progressively.

Use Server-Sent Events initially.

The frontend should display:
- Response generation status.
- Streaming text.
- Citations.
- Errors.
- Completion state.

---

# MODULE H: ASSESSMENT ENGINE

The assessment engine evaluates student understanding.

## H1. Question Sources

Questions can come from:

- Uploaded suggestion papers.
- Previous-year papers.
- Uploaded textbooks.
- AI-generated questions.
- Instructor-created questions.

Extracted and generated questions must preserve their source.

## H2. Question Classification

Each question should have:

- Question text.
- Course.
- Unit.
- Topic.
- Marks.
- Question type.
- Difficulty.
- Source document.
- Source page.
- Correct answer or marking rubric.

Question types:

- MCQ.
- True/False.
- Short answer.
- Long answer.
- Numerical.
- Fill in the blanks.
- Descriptive.

## H3. Question Extraction

When users upload suggestion papers or previous-year papers, the system should extract questions and map them to syllabus topics.

Users should be able to review and correct extracted questions.

## H4. Quiz Generation

Users can generate quizzes based on:

- Entire course.
- Individual unit.
- Individual topic.
- Selected difficulty.
- Selected marks.
- Selected question type.

## H5. Answer Evaluation

MCQs should be graded deterministically.

Descriptive answers should be evaluated using structured rubrics.

For example, a five-mark question can have:
- Conceptual accuracy: 2 marks.
- Explanation: 1 mark.
- Example: 1 mark.
- Presentation: 1 mark.

The evaluator should provide:
- Score.
- Correct concepts.
- Missing concepts.
- Incorrect statements.
- Suggested improvements.
- Reference answer.

AI-generated scores should be presented as estimated assessments, not guaranteed university grading.

## H6. Progress Tracking

Track:
- Questions attempted.
- Correct answers.
- Accuracy.
- Weak topics.
- Strong topics.
- Last studied date.
- Revision schedule.

---

# MODULE I: LEARNING ANALYTICS

The dashboard should provide an overview of student progress.

Required metrics:

- Courses enrolled in.
- Topics completed.
- Topics remaining.
- Lessons generated.
- Quiz attempts.
- Average quiz accuracy.
- Weak topics.
- Revision due.

Progress must be calculated per user, not simply at the workspace level.

A future version can implement spaced repetition and adaptive learning recommendations.

---

# 6. COMPLETE SYSTEM ARCHITECTURE

Use a modular monolith architecture initially.

Do not introduce microservices in the first release.

## 6.1 Frontend

Technology:
- React.
- Vite.
- TypeScript.
- Tailwind CSS.
- shadcn/ui.
- TanStack Query.
- React Router.
- Mermaid.js.
- KaTeX.

Frontend responsibilities:
- Authentication.
- Workspace management.
- Course management.
- Document uploads.
- Syllabus navigation.
- Lesson rendering.
- AI tutor.
- Assessments.
- Progress dashboards.

## 6.2 Backend

Technology:
- Python.
- FastAPI.
- SQLAlchemy 2.
- Pydantic.
- Alembic.

Backend responsibilities:
- Authentication and authorization.
- Workspace management.
- Course and syllabus management.
- Document processing.
- RAG.
- Web research.
- Lesson generation.
- AI tutor.
- Assessments.
- Analytics.

## 6.3 Database

Use PostgreSQL with pgvector.

Core entities:

- users
- workspaces
- workspace_members
- courses
- syllabi
- units
- topics
- documents
- document_chunks
- research_jobs
- research_sources
- lessons
- lesson_versions
- lesson_citations
- tutor_sessions
- tutor_messages
- questions
- quizzes
- quiz_questions
- quiz_attempts
- topic_progress
- jobs
- job_events
- llm_usage
- audit_logs

All tenant-owned data must include appropriate workspace relationships.

Implement Row-Level Security and backend permission checks.

## 6.4 Background Processing

Use Redis and Celery.

Background tasks include:
- Document ingestion.
- OCR.
- Embedding generation.
- Syllabus parsing.
- Batch lesson generation.
- Web research.
- Question extraction.
- Large-scale assessments.

Tasks must support:
- Retries.
- Failure tracking.
- Status updates.
- Idempotency where practical.

## 6.5 Object Storage

Use S3-compatible storage.

Store:
- Original documents.
- Extracted assets when required.
- Generated exports.
- Other uploaded resources.

Use private buckets and signed access URLs.

## 6.6 AI Provider Abstraction

Implement a provider abstraction.

Initially support:
- OpenAI.
- Google Gemini.
- Local OpenAI-compatible inference endpoints.

The application must not depend on one specific provider's SDK throughout the codebase.

Support:
- Chat completion.
- Structured output.
- Embeddings.
- Token usage.
- Model configuration.

Provider credentials must remain server-side.

---

# 7. API REQUIREMENTS

All API routes must use:

/api/v1

## Authentication

POST /auth/register  
POST /auth/login  
POST /auth/refresh  
POST /auth/logout  

GET /users/me  
PATCH /users/me  

## Workspaces

POST /workspaces  
GET /workspaces  
GET /workspaces/{id}  
PATCH /workspaces/{id}  
DELETE /workspaces/{id}  

GET /workspaces/{id}/members  
POST /workspaces/{id}/invitations  
DELETE /workspaces/{id}/members/{user_id}  

## Courses and syllabus

POST /workspaces/{id}/courses  
GET /courses/{id}  
PATCH /courses/{id}  

POST /courses/{id}/syllabus  
GET /courses/{id}/syllabus  
POST /courses/{id}/syllabus/parse  

GET /courses/{id}/units  
GET /courses/{id}/topics  

## Documents

POST /workspaces/{id}/documents  
GET /workspaces/{id}/documents  
GET /documents/{id}  
DELETE /documents/{id}  
POST /documents/{id}/reprocess  
GET /documents/{id}/status  

## Lessons

POST /topics/{id}/lessons/generate  
GET /topics/{id}/lessons  
GET /lessons/{id}  
POST /lessons/{id}/regenerate  
GET /lessons/{id}/versions  
POST /lessons/{id}/publish  
POST /lessons/{id}/feedback  

## Research

POST /topics/{id}/research  
GET /research/{id}  
GET /research/{id}/sources  
POST /research/{id}/refresh  

## Tutor

POST /tutor/sessions  
GET /tutor/sessions  
GET /tutor/sessions/{id}  
POST /tutor/sessions/{id}/messages  
GET /tutor/sessions/{id}/messages  

## Assessments

POST /topics/{id}/quizzes  
GET /quizzes/{id}  
POST /quizzes/{id}/attempts  
GET /attempts/{id}/results  

## Analytics

GET /courses/{id}/progress  
GET /users/me/learning-analytics  

## Job Events

GET /jobs/{id}  
GET /jobs/{id}/events  

The SSE endpoint must expose real job stages and completion/failure events.

All endpoints must implement authorization and input validation.

---

# 8. RECOMMENDED PROJECT STRUCTURE

Use the following repository organization.

personal-ai-tutor/

backend/
  app/
    main.py
    config.py
    dependencies.py

    core/
      security.py
      permissions.py
      middleware.py
      logging.py
      exceptions.py

    modules/
      auth/
      users/
      workspaces/
      courses/
      syllabus/
      documents/
      rag/
      research/
      lessons/
      tutor/
      assessments/
      analytics/

    ai/
      providers/
        base.py
        openai.py
        gemini.py
        local.py
      embeddings/
      prompts/
      schemas/

    orchestration/
      learning_pipeline.py
      lesson_pipeline.py
      research_pipeline.py
      tutor_pipeline.py

    workers/
      celery_app.py
      ingestion_tasks.py
      generation_tasks.py
      research_tasks.py

    database/
      models/
      repositories/
      migrations/
      session.py

  tests/
  requirements.txt
  Dockerfile

frontend/
  src/
    app/
    components/
      ui/
      diagrams/
      lesson-blocks/
      tutor/
      document-viewer/

    features/
      authentication/
      workspaces/
      courses/
      syllabus/
      documents/
      lessons/
      tutor/
      quizzes/
      analytics/

    hooks/
    lib/
    services/
    types/
    routes/

  package.json
  Dockerfile

infrastructure/
  docker-compose.yml
  nginx/
  deployment/

docs/
  architecture.md
  api-specification.md
  database-schema.md
  prompts.md

scripts/
  seed.py
  migrate.py

.env.example
.gitignore
README.md

Each backend module should follow a consistent separation of:
- router.py
- service.py
- repository.py
- schemas.py
- models.py

Do not place all application logic in route handlers.

---

# 9. UI/UX REQUIREMENTS

## 9.1 Design Philosophy

The platform should feel like a modern digital learning environment, not a generic AI chatbot.

Design principles:

- Clean and minimal.
- Comfortable reading experience.
- Strong visual hierarchy.
- Clear typography.
- Generous whitespace.
- Responsive layout.
- Visually distinct content blocks.
- Minimal distractions.
- Accessible contrast.

Avoid:
- Long uninterrupted paragraphs.
- Excessive gradients.
- Overly decorative dashboards.
- Too many nested cards.
- Unnecessary animations.

## 9.2 Primary Screens

### Screen 1: Dashboard

Display:
- Welcome section.
- My workspaces.
- Recent courses.
- Continue learning.
- Recent lessons.
- Study progress.

### Screen 2: Workspace

Display:
- Workspace name.
- Members.
- Courses.
- Documents.
- Shared learning resources.
- Activity.

### Screen 3: Course Workspace

Display:
- Course overview.
- Syllabus.
- Units.
- Topics.
- Uploaded documents.
- Generation progress.

### Screen 4: Learning Page

This is the most important screen.

It should include:
- Topic title.
- Learning objectives.
- Estimated reading time.
- Structured lesson content.
- Diagrams.
- Tables.
- Examples.
- Citations.
- Quick revision.
- Practice questions.

Include a contextual AI tutor panel or expandable tutor interface.

### Screen 5: AI Tutor

Display:
- Conversation history.
- Current course and topic context.
- Message interface.
- Streaming responses.
- Source citations.
- Suggested follow-up questions.
- Learning mode selector.

### Screen 6: Assessment

Display:
- Question.
- Marks.
- Difficulty.
- Answer input.
- Submission.
- Evaluation.
- Feedback.
- Reference answer.

### Screen 7: Progress Dashboard

Display:
- Topic completion.
- Unit completion.
- Quiz accuracy.
- Weak areas.
- Revision requirements.

---

# 10. NON-FUNCTIONAL REQUIREMENTS

## 10.1 Performance

Initial engineering targets:

- Normal API requests: p95 under 500 ms, excluding external AI and long-running operations.
- Dashboard initial load: under 3 seconds on a reasonable connection.
- Tutor response: stream output as soon as available.
- Document processing: asynchronous.
- Large generation jobs: asynchronous.
- Pagination for resource listings.

These are target budgets, not guarantees independent of hosting and provider latency.

## 10.2 Scalability

The architecture should support independent scaling of:

- API processes.
- Background workers.
- Document ingestion.
- Lesson generation.

Do not introduce microservices until actual workload justifies them.

## 10.3 Reliability

Requirements:
- Structured logs.
- Error monitoring.
- Task retries.
- Database backups.
- Graceful API errors.
- Generation failure handling.
- Idempotent job submission where appropriate.

## 10.4 Security

Requirements:
- Password hashing.
- Secure authentication.
- RBAC.
- Database tenant isolation.
- Upload validation.
- Private file storage.
- Signed URLs.
- Rate limiting.
- Audit logging.
- Prompt injection defenses.
- SSRF protection.
- Secret management.

## 10.5 Privacy

- Personal conversations remain private.
- Workspace content is accessible only to authorized members.
- Users can delete their own data where permitted.
- Deleted documents must be removed from the active retrieval index.
- Provider data usage and retention policies must be reviewed before launch.

---

# 11. AI QUALITY REQUIREMENTS

The platform must prioritize correctness over generating impressive-looking answers.

## 11.1 Grounded Responses

When academic material exists, use it as the primary evidence source.

Never invent citations.

## 11.2 Source Transparency

Clearly distinguish:

- Uploaded-document information.
- External web information.
- AI-generated examples and explanations.

## 11.3 Syllabus Relevance

Every generated academic lesson should be associated with a syllabus topic wherever a syllabus is available.

Supplementary information should be distinguishable from required syllabus material.

## 11.4 Educational Quality

Generated lessons should:
- Explain concepts progressively.
- Use examples.
- Avoid unnecessary jargon.
- Include relevant visuals.
- Avoid redundant explanations.
- Match the selected learning depth.

## 11.5 Content Validation

Before publishing a lesson, validate:
- JSON schema.
- Required sections.
- Citation references.
- Diagram syntax.
- Mathematical expressions.
- Topic relevance.
- Missing content.

Failed validation should trigger a bounded retry or return a clear failure state.

---

# 12. COST MANAGEMENT

The platform must track AI consumption.

Track:
- Input tokens.
- Output tokens.
- Embedding usage.
- Search API calls.
- Model name.
- Provider.
- Generation type.
- Workspace.
- User.
- Estimated cost.

Optimization requirements:

1. Cache embeddings by content checksum and model version.
2. Reuse existing research results when appropriate.
3. Avoid unnecessary lesson regeneration.
4. Use smaller models for classification and metadata extraction.
5. Use more capable models for complex content generation.
6. Implement workspace and user usage limits.
7. Limit search and generation retries.

Shared lesson generation should be reusable across workspace members.

Personal learning interactions must remain isolated.

---

# 13. DEPLOYMENT ARCHITECTURE

Initial deployment:

Frontend:
- Vercel.

Backend:
- Railway or Render.

Workers:
- Railway or Render.

Database:
- Managed PostgreSQL with pgvector.

Cache:
- Managed Redis.

Storage:
- Cloudflare R2 or AWS S3.

Monitoring:
- Sentry.
- Structured application logs.

All services must be containerized where appropriate.

Provide:
- Dockerfile for backend.
- Dockerfile for frontend.
- Docker Compose for local development.
- Environment variable documentation.
- Database migration instructions.
- Deployment instructions.

Do not require a dedicated GPU server for the initial release.

Hosted LLM APIs should be used initially.

---

# 14. IMPLEMENTATION PHASES

Development must happen incrementally.

The application must remain runnable after each phase.

## PHASE 1: FOUNDATION

Objectives:
- Repository setup.
- Docker configuration.
- FastAPI initialization.
- React initialization.
- PostgreSQL connection.
- Alembic migrations.
- Authentication.
- User management.
- Workspace management.
- RBAC.
- Course management.

Deliverable:
A functioning authenticated application where users can create workspaces, invite others and create courses.

## PHASE 2: DOCUMENT AND KNOWLEDGE ENGINE

Objectives:
- File upload.
- Object storage.
- Document processing.
- PDF/DOCX/PPTX extraction.
- OCR fallback.
- Background task queue.
- Chunking.
- Embeddings.
- pgvector integration.
- Hybrid retrieval.
- Citation metadata.

Deliverable:
Users can upload academic materials and retrieve relevant passages with source references.

## PHASE 3: SYLLABUS AND RESEARCH

Objectives:
- Syllabus parser.
- Unit/topic extraction.
- Editable syllabus hierarchy.
- Topic mapping.
- Search provider integration.
- Research query generation.
- Page extraction.
- Source evaluation.
- Research citations.

Deliverable:
The system can understand a syllabus and supplement uploaded knowledge through web research.

## PHASE 4: CONTENT GENERATION

Objectives:
- Structured lesson schema.
- Lesson generation.
- Batch generation.
- On-demand enrichment.
- Mermaid support.
- KaTeX support.
- Tables and examples.
- Citation rendering.
- Lesson versioning.
- Content validation.

Deliverable:
Students can generate complete, structured study material for syllabus topics.

## PHASE 5: AI TUTOR AND ASSESSMENTS

Objectives:
- Tutor sessions.
- Streaming.
- Context-aware RAG.
- Learn mode.
- Doubt mode.
- Socratic mode.
- Exam mode.
- Revision mode.
- Question generation.
- Quiz evaluation.
- Topic progress.

Deliverable:
A functional personal AI tutor.

## PHASE 6: PRODUCTIZATION

Objectives:
- Workspace sharing.
- Invitation management.
- Personal dashboards.
- Shared learning resources.
- Analytics.
- Usage tracking.
- Monitoring.
- Security testing.
- Production deployment.

Deliverable:
A multi-user cloud-based learning platform.

---

# 15. ACCEPTANCE CRITERIA

The initial release is considered complete only when the following end-to-end workflow works.

## Workflow 1: User onboarding

1. A student registers.
2. Creates a workspace.
3. Creates a course.
4. Invites another student.
5. The invited student joins.
6. Both users can access authorized shared resources.

## Workflow 2: Document ingestion

1. Student uploads a PDF textbook.
2. File is stored.
3. Background ingestion starts.
4. Text is extracted.
5. Chunks are generated.
6. Embeddings are stored.
7. Document status becomes ready.
8. Relevant chunks can be retrieved.

## Workflow 3: Syllabus processing

1. Student uploads a syllabus.
2. System extracts units and topics.
3. Structured syllabus is generated.
4. Student reviews and edits it.
5. Topics become available in the course workspace.

## Workflow 4: Lesson generation

1. Student selects a topic.
2. System retrieves relevant uploaded materials.
3. Evidence sufficiency is evaluated.
4. Web research runs if necessary.
5. Evidence is consolidated.
6. Structured lesson is generated.
7. Diagrams are validated.
8. Citations are attached.
9. Lesson is saved.
10. Frontend renders the complete learning experience.

## Workflow 5: AI tutoring

1. Student opens a topic.
2. Starts a tutor session.
3. Asks a question.
4. System retrieves relevant material.
5. Tutor generates a contextual response.
6. Citations are displayed.
7. Student asks follow-up questions.
8. Conversation history is preserved.

## Workflow 6: Assessment

1. Student generates a quiz.
2. Questions are displayed.
3. Student submits answers.
4. Objective questions are graded.
5. Descriptive questions receive rubric-based evaluation.
6. Results are saved.
7. Topic progress is updated.

## Workflow 7: Tenant isolation

1. User A creates a private workspace.
2. User B attempts to access its resources.
3. Access is denied.
4. User A invites User B.
5. User B receives only the permissions granted by the workspace role.
6. User B still cannot access User A's private conversations or personal progress.

---

# 16. TESTING STRATEGY

Implement automated tests at every layer.

### Backend
- Unit tests.
- API integration tests.
- Database tests.
- Authorization tests.
- Tenant isolation tests.
- Job processing tests.

### RAG
- Retrieval Recall@K.
- Mean Reciprocal Rank.
- Metadata filtering accuracy.
- Citation correctness.

### AI Generation
- Structured output validation.
- Syllabus coverage.
- Citation grounding.
- Diagram rendering.
- Educational quality.

### Frontend
- Component tests.
- API integration tests.
- Loading states.
- Error states.
- Responsive layout.
- End-to-end user workflows.

Create a small manually reviewed academic benchmark using actual syllabus documents, textbooks and previous-year questions.

Do not rely exclusively on LLM-as-judge evaluations.

---

# 17. OUT OF SCOPE FOR INITIAL RELEASE

The following features must not delay the initial product:

- Native Android/iOS applications.
- Voice-based tutoring.
- Real-time collaborative editing.
- Advanced handwritten mathematical recognition.
- Video lecture generation.
- AI-generated animations.
- Advanced teacher administration.
- Institution-wide LMS integrations.
- Payment and subscription systems.
- Social learning feeds.
- Public course marketplaces.
- Autonomous multi-agent systems.
- Dedicated GPU inference infrastructure.

These can be considered after the core learning workflow is stable.

---

# 18. DEVELOPMENT RULES AND ENGINEERING CONSTRAINTS

These requirements are mandatory.

1. Do not implement the entire application in one file.
2. Follow the documented modular architecture.
3. Separate routers, services, repositories, schemas and database models.
4. Use type hints throughout Python code.
5. Use Pydantic for API validation.
6. Use SQLAlchemy 2 for database access.
7. Use Alembic for migrations.
8. Do not hardcode API keys or credentials.
9. Maintain an `.env.example` file.
10. Do not store uploaded documents directly inside PostgreSQL.
11. Do not run document ingestion synchronously inside API requests.
12. Do not make external LLM calls directly inside route handlers.
13. Implement provider abstraction.
14. Do not allow cross-workspace document retrieval.
15. Implement server-side authorization for every protected resource.
16. Never trust LLM-generated citations without checking their source references.
17. Never execute arbitrary LLM-generated HTML or JavaScript.
18. Keep generated content separate from original knowledge sources.
19. Version lessons and prompts.
20. Implement proper error handling and logging.
21. Provide database migrations for every schema change.
22. Include tests for critical business logic.
23. Keep the application runnable after every implementation phase.
24. Do not replace a functioning implementation with mock data.
25. Do not leave critical features as empty placeholders while claiming they are complete.

### Development Workflow

Before implementing each major module:

1. Inspect the existing repository.
2. Understand the existing architecture.
3. Identify dependencies.
4. Define the module's interfaces.
5. Implement backend logic.
6. Implement database migrations.
7. Write tests.
8. Integrate the frontend.
9. Run the relevant tests.
10. Update project documentation.

Do not unnecessarily rewrite existing working code.

If an implementation decision differs from this PRD, document the reason before proceeding.

---

# 19. SUCCESS METRICS

The initial product should be evaluated using:

### Knowledge Engine
- Document ingestion success rate.
- Retrieval relevance.
- Citation accuracy.
- Retrieval latency.

### Content Generation
- Lesson generation success rate.
- Valid diagram percentage.
- Syllabus coverage.
- Lesson regeneration rate.
- Human-reviewed content quality.

### Learning Experience
- Lessons completed.
- Quiz participation.
- Quiz accuracy improvement.
- Topics revised.
- Student feedback.

### Product Reliability
- API availability.
- Background job success rate.
- Cross-tenant access violations.
- Average generation cost.
- Error rate.

Initial targets should be established after the first real academic evaluation dataset is available.

---

# 20. FINAL PRODUCT DEFINITION

Personal AI Tutor is a multi-user, cloud-based educational platform that converts academic resources into structured and interactive learning experiences.

Its primary differentiator is the integration of three capabilities:

**1. Knowledge Retrieval**

It understands user-provided academic materials and retrieves relevant information with precise source attribution.

**2. Intelligent Research**

It identifies missing information and supplements the knowledge base through external research.

**3. Educational Content Generation**

It transforms the gathered evidence into readable lessons containing explanations, diagrams, examples, tables, formulas, revision notes and assessments.

These capabilities are combined with a contextual AI tutor and personalized assessment system.

The result should be an application where a student can upload an entire semester syllabus and its associated study materials, generate structured lessons for every topic, ask questions, practice examinations and track learning progress.

**The ultimate product objective: A student should not need to manually search through dozens of PDFs, websites and notes to understand a topic. The platform should organize that process into one coherent learning experience.**

---

# 21. INSTRUCTIONS FOR THE DEVELOPMENT AGENT

You are responsible for implementing this product according to the requirements in this PRD.

Act as a senior software architect and full-stack AI engineer.

Your priorities, in order, are:

1. Correct architecture.
2. Data integrity and tenant isolation.
3. Functional end-to-end workflows.
4. Reliable RAG and source attribution.
5. High-quality educational content.
6. Clean and maintainable code.
7. Good user experience.
8. Performance and cost optimization.

Do not attempt to build everything simultaneously.

Start by:

1. Inspecting the repository and existing files.
2. Producing a concise implementation plan.
3. Establishing the project structure.
4. Defining database models and migrations.
5. Implementing Phase 1.
6. Testing Phase 1 before proceeding.

Maintain a development checklist and update it as features are completed.

At the end of each phase, report:

- Features implemented.
- Files created or modified.
- Database changes.
- Tests executed.
- Known issues.
- Remaining tasks.
- Instructions for running the application.

**Important:** The PRD describes the intended complete product. Implement it incrementally. Never sacrifice a functioning, tested foundation in an attempt to implement all features at once.

The final result must be a real, runnable application, not a collection of frontend mockups or disconnected API endpoints.