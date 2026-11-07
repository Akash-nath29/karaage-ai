---
version: 1
slug: "frontend-src-features-study-studysession-tsx"
primary_target: "frontend/src/features/study/StudySession.tsx"
related_targets: ["frontend/src/features/courses/CoursePage.tsx","frontend/src/features/workspaces/WorkspacePage.tsx","frontend/src/features/dashboard/DashboardPage.tsx"]
---

# Study flow (course home, study session, workspace, dashboard)

Mode: Operate. Scope: the app's whole learning flow, restructured; the visual world stays as it is (confirmed 2026-11-08: "flow only, keep the look"; "restructure freely", every feature stays). Decision log: docs/decisions.md D38.

Audience and job: organisers set a course up in dependency order (mostly on a laptop); learners study topic by topic and, near exams, revise weak topics (phone and laptop). Both matter equally (PRODUCT.md).

## Direction contract

THESIS: Every topic is one sitting (Learn, Check, Review, then the next stop), and a course reads as a line of topics with exactly one next stop. It refuses the category default: a course page that stacks every feature as an equal panel, and a topic page that lists lessons, quizzes and research side by side with no order.

OWN-WORLD: Today's look, unchanged: white ground, near-black text, neutral greys, Geist, the existing Button, Badge, Card, Input and native selects. New pieces speak the same language: a station line (a thin neutral rail; stations as dots: filled = done, ringed = you are here or the next stop, hollow = to learn, amber ring = revise), route tabs underlined for the current stage, and one primary button per screen.

STORY: An organiser opens a new course and sees a five-step setup checklist in the order things depend on each other (upload the syllabus, confirm topics, add notes and papers, lessons being written, invite), each step with its state and its action inline; done, it collapses to one line. A learner sees one Next stop and the syllabus as station lines. A topic opens as a session: the lesson leads, "Check yourself" follows, the review shows what was missed with reference answers, then sends them on to the next stop. The tutor is beside every stage.

FIRST VIEWPORT: Session on desktop: breadcrumb (course, unit), topic title with its progress badge, the unit's station line across the full width, the Learn, Check and Review tabs, then the lesson in a reading column (about 70ch) with a sticky tutor rail on the right. The primary action is "Check yourself" at the lesson's end, and "Next stop" on Review. On a phone: one column, the stage tabs stay visible, and the tutor opens as a sheet from a floating button. Course home: title, the setup checklist (organisers, until done), the Next stop card, then each unit's station line, with the Topics, Practice, Materials and Settings tabs above.

FORM: Study session, 4th on my ordered list (guided path, study/manage split, syllabus map, study session, topic board, up-next queue); seed key f98ebdce. Raise from the metro diagram: topics are stations on one line. Signature interaction: when a check is marked, that station fills and the next-stop ring moves on to the following station (one short ease-out, instant under reduced motion).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
