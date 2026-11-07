# Product

<!-- impeccable:product-schema 1 -->

`PRD.md` is the source of truth for requirements; `docs/decisions.md` records every deviation. This file holds the durable product facts design work needs.

## Platform

web

## Users

University students (undergraduate and postgraduate) preparing for semester exams. The evidence on hand is an Indian university curriculum (`test_material/AIML-R23.pdf`, courses with codes like AM701).

Two jobs matter equally (confirmed 2026-11-08), often done by different people in the same workspace:

- **The organiser** (workspace owner, admin or editor; a solo student, class rep, topper or teacher) sets up a course: creates the workspace and course, uploads the syllabus, notes, textbooks and previous-year question papers, confirms the parsed syllabus, and shares lessons.
- **The learner** (everyone, including viewers who joined by invite) studies: reads lessons, asks the tutor, takes quizzes, reviews feedback and tracks progress.

A solo student is both, in sequence. In a study group, most members are only learners.

Device split (confirmed): setup and organising happen mostly on a laptop; studying (lessons, tutor, quizzes) happens on both phone and laptop.

## Product Purpose

Turn a student's own syllabus and materials into structured lessons, a tutor and practice, so they understand each topic and are ready for the exam. PRD philosophy: "Knowledge first. Teaching second. Assessment third." The loop: understand what to learn, explain it, test it, find the gaps, recommend what to study next.

Success: a learner always knows what to study next, and can see they are covering the syllabus and closing weak areas before the exam.

## Positioning

Lessons and answers are grounded in the student's own syllabus and uploaded materials, organised by the syllabus's units and topics, with every block showing where it came from (your materials, the web, or the AI). Exam-aware: previous-year questions feed a question bank, answers are marked against 2/5/10-mark rubrics, and progress points at weak topics. It is not a chatbot that returns long text.

## Operating Context

- Setup sequence, each step depending on the one before: workspace → course → upload materials (the syllabus document first) → parse and confirm the syllabus (units and topics) → lessons are written for every topic in the background → materials are matched to topics.
- Study loop per topic: read the lesson (sections, diagrams, formulas, worked examples, quick revision, flashcards) → ask the tutor about doubts → quiz → feedback with a reference answer → progress (studied, accuracy, weak areas, revise-by dates).
- Two phases (confirmed): steady learning through the semester (topic by topic), then exam crunch as the exam approaches (previous-year questions, answers by marks, fast revision of weak topics).
- Background jobs take minutes (OCR and indexing, syllabus parsing, lesson generation, research) and show live progress; nothing may block on them.

## Capabilities and Constraints

- Roles per workspace: viewer < editor < admin < owner (PRD §4.2, decision A11). Tutor conversations, quizzes, progress and private lessons are personal: nobody else sees them.
- Built: accounts and email confirmation, workspaces, invitations, courses, document upload (OCR for scans), syllabus parsing and an editable review, lessons at several depths with versions and "ask for more", topic research with citations, the AI tutor (doubt, learn, Socratic, exam, revision modes), question bank from question papers, quizzes with AI marking, progress, dashboard analytics, AI usage budgets.
- Production uploads are capped at 4 MB per file (decision D37).
- Terminology in use: workspace, course, syllabus, unit, topic, lesson, study materials, question bank, quiz, tutor, progress.

## Brand Commitments

Name: Karaage. No logo, palette or voice guide beyond the name and `frontend/public/favicon.svg`.

## Evidence on Hand

- A real curriculum: `test_material/AIML-R23.pdf`; benchmark fixtures in `backend/tests/benchmark/` (a synthetic question paper is labelled SYNTHETIC).
- No users, testimonials, usage figures or outcomes exist yet. Do not fabricate any.

## Product Principles

1. **Always one next step.** Every screen shows where the user is in the sequence (set up → learn → practise → review) and the single most useful next action.
2. **Setup is a phase; studying is the product.** Organiser tasks appear when needed and get out of the way afterwards; learners never wade through controls they can't use.
3. **Show the source.** Generated content always says whether it came from the student's materials, the web or the AI.
4. **Slow work runs in the background, visibly.** Long AI jobs never block the user and always show progress.
5. **Aware of the phase.** The same course serves topic-by-topic learning and exam-crunch revision.

## Accessibility & Inclusion

PRD §9.1: accessible contrast, comfortable reading, no long uninterrupted paragraphs, minimal distraction. Lessons are read on phones as well as laptops.
