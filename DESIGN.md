---
name: Karaage
description: Syllabus-grounded lessons, tutor and practice for university exam study.
colors:
  primary: "oklch(0.205 0 0)"
  primary-foreground: "oklch(0.985 0 0)"
  foreground: "oklch(0.145 0 0)"
  background: "oklch(1 0 0)"
  card: "oklch(1 0 0)"
  secondary: "oklch(0.97 0 0)"
  muted: "oklch(0.97 0 0)"
  muted-foreground: "oklch(0.556 0 0)"
  border: "oklch(0.922 0 0)"
  input: "oklch(0.922 0 0)"
  ring: "oklch(0.708 0 0)"
  destructive: "oklch(0.577 0.245 27.325)"
  revise-amber: "oklch(0.666 0.179 58.318)"
  revise-amber-wash: "oklch(0.987 0.022 95.277)"
  revise-amber-text: "oklch(0.555 0.163 48.998)"
typography:
  headline:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: "2rem"
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 500
    lineHeight: "1.75rem"
  lesson-section:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: "1.75rem"
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.625
  body-ui:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.25rem"
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: "1rem"
rounded:
  sm: "0.375rem"
  md: "0.5rem"
  lg: "0.625rem"
  xl: "0.875rem"
  2xl: "1.125rem"
  4xl: "1.625rem"
  full: "9999px"
spacing:
  card: "1rem"
  card-sm: "0.75rem"
  panel: "1.25rem"
  stack-tight: "0.5rem"
  stack: "0.75rem"
  stack-loose: "1rem"
  section: "2rem"
  page: "3rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.lg}"
    padding: "0 10px"
    height: "2rem"
  button-primary-hover:
    backgroundColor: "oklch(0.205 0 0 / 80%)"
  button-primary-lg:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.lg}"
    padding: "0 10px"
    height: "2.25rem"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    height: "2rem"
  button-ghost-hover:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.foreground}"
  badge:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.4xl}"
    padding: "2px 8px"
    height: "1.25rem"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.xl}"
    padding: "{spacing.card}"
  panel:
    backgroundColor: "{colors.background}"
    rounded: "{rounded.xl}"
    padding: "{spacing.panel}"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    padding: "4px 10px"
    height: "2rem"
  route-tab:
    textColor: "{colors.muted-foreground}"
    padding: "10px 12px"
    typography: "{typography.body-ui}"
  route-tab-active:
    textColor: "{colors.foreground}"
  station-dot:
    rounded: "{rounded.full}"
    size: "0.875rem"
---

# Design System: Karaage

## Overview

**Creative North Star: "Graphite on Paper"**

Karaage is an achromatic, flat, quiet study tool: near-black graphite on white, one geometric sans (Geist), hairline borders and roomy vertical rhythm. Colour carries meaning, not mood. The only saturated hue in the app chrome is amber, and it means one thing: this topic needs revising. Destructive red marks errors and deletion. Everything else is a step on the neutral ramp.

Density is calm. Pages sit in a single narrow column (56rem), and the study session widens to 72rem only to make room for the tutor rail. Sections are separated by space and hairlines, not by boxes inside boxes. Each screen has one filled primary button for its main next step, and the other actions are outline, ghost or link buttons.

The system's signature is the **station line**: a course's topics drawn as stops on a line. Filled, half-filled, amber and hollow dots show progress, and one ringed dot marks the course's single next stop. The same next stop is named in the panel on the course home, on the dashboard and inside the session, so the learner never sees two competing "next" answers.

**Key Characteristics:**
- Achromatic OKLCH neutrals; graphite primary (oklch 0.205) on white.
- One family, Geist Variable, for every role; hierarchy comes from size and weight (500/600), never from case or tracking.
- Flat: depth comes from 1px rings and borders. There is one shadow in the app, on the floating phone tutor button.
- Gently rounded rectangles (0.625rem controls, 0.875rem panels), with pill badges and round station dots.
- One filled primary action per view; everything else steps down.

## Colors

A neutral graphite-and-white palette with one semantic hue (amber for revise) and one alarm hue (red for destructive actions and errors).

### Primary
- **Graphite** (primary): filled buttons, the default badge (for example "Next stop"), the active route-tab underline, and the filled "done" station dot (which uses foreground, a step darker). Hover lightens it to 80% opacity.

### Tertiary
- **Revise Amber** (revise-amber, Tailwind `amber-600`): the border of a "revise" station dot and of the "Worth another pass" panel (at 40% opacity). *Convention, not a CSS token:* it is written as Tailwind palette utilities, not as a custom property in `index.css`.
- **Amber Wash** (revise-amber-wash, `amber-50`; `amber-100` inside the dot): the fill behind revise states.
- **Amber Ink** (revise-amber-text, `amber-700`): "Revise · last check 30%" metadata text.

### Neutral
- **Ink** (foreground): body text, headings, the current tab, done dots and the next-stop ring.
- **Paper** (background, card): the page and card surfaces; both are pure white.
- **Mist** (muted, secondary): ghost and outline hover, card footers, the "Done reading?" hand-off panel at 40%, the verify banner at 50%, and code blocks in lessons.
- **Pencil** (muted-foreground): secondary text, counts ("2 of 4 topics completed"), inactive tabs, hollow todo dots (at 60%) and breadcrumbs.
- **Hairline** (border, input): every divider, panel border, field stroke and the station line's track.
- **Focus Grey** (ring): focus rings, always at 50% opacity and 3px.
- **Alarm Red** (destructive): error text and destructive buttons and badges (red text on a 10% red wash). The "revision required" progress badge also uses it.

### Named Rules
**The Amber Means Revise Rule.** Amber appears only where a topic needs another pass: the revise dot, its metadata text and the revise outcome panel. It is never decoration or a generic warning.

**The Graphite Primary Rule.** The primary is near-black, not a brand hue. Emphasis comes from filling a shape with graphite, not from adding colour.

Lesson content has its own callout hues (Note in sky, Tip in emerald, Exam tip in violet, each a 600 border at 40% over a 50 wash, plus green for a correct answer in an interactive question). These are a lesson-block convention scoped to `components/lesson-blocks/`, not app-chrome colours.

The `.dark` token set in `index.css` and the `dark:` variants in the components are dormant: nothing in the app applies the `.dark` class. The shipped system is light-only.

## Typography

**Display Font:** none (no separate display face)
**Body Font:** Geist Variable (with sans-serif); `--font-heading` aliases it.

**Character:** One neutral geometric sans used everywhere. Headings are only slightly heavier and larger than body text, which keeps the interface sober and keeps attention on the lesson.

### Hierarchy
- **Headline** (600, 1.5rem, tracking -0.025em, balanced wrapping): one page title per page (course, workspace, topic, dashboard). A few older pages omit the tight tracking.
- **Lesson section** (600, 1.25rem): section headings inside a lesson.
- **Title** (500, 1.125rem): section headings on a page, and panel headings ("Next stop: Thrashing", "Done reading?", "Set up this course").
- **Subhead** (500, 1rem): unit headings ("Unit 1: Process Management"), setup-step titles and the tutor rail heading. Convention: weight 500 at body size.
- **Body** (400, 1rem, relaxed 1.625 leading, grid gap 0.75rem): lesson markdown (`.md`). Prose is capped at `max-w-prose` (65ch).
- **Body UI** (400, 0.875rem): the dominant UI size: descriptions, metadata, buttons, tabs and form labels.
- **Label** (500, 0.75rem): badges and station names on the unit line. The station marker under a dot ("Next stop", "You're here") is 11px.
- Numbers that count or score use `tabular-nums`. The one large figure is the results score (600, 2.25rem), a one-off rather than a role.

### Named Rules
**The No-Shouting Rule.** No uppercase and no letter-spaced labels anywhere in the build. Hierarchy is size plus weight 500/600 only.

## Layout

- **Container:** a centred column, `max-w-4xl` (56rem) with 1.5rem side padding and 2rem top and bottom padding. Study-session routes (`/topics/:id/*`) widen to `max-w-6xl` (72rem). The header matches the column width and sits over a full-width bottom hairline.
- **Spacing rhythm:** Tailwind's 0.25rem base. Inline clusters use 0.5rem gaps (the most common); stacks inside a component use 0.75 to 1rem; page sections use 2rem, 2.5rem or 3rem. Layout is built from CSS grid with `gap`, not margins.
- **Panels:** 1.25rem padding. Cards use 1rem (0.75rem when small).
- **Action rows:** a panel with one primary action is a two-column grid from `sm` up (`minmax(0,1fr) auto`, vertically centred), with the action on the right. Below `sm` it stacks.
- **Study session:** a reading column plus a 22rem tutor rail from `lg` (64rem) up, with a 2.5rem gap. The rail is sticky (top 1rem) and scrolls internally up to `100dvh - 2rem`. Below `lg` the rail becomes a fixed "Ask the tutor" button at the bottom right that opens a bottom-sheet `<dialog>` at 85dvh. The stage tabs (Learn, Check, Review) stick to the top of the reading column.
- **Wrapping:** headers, badge rows and tab lists use `flex-wrap` rather than horizontal overflow. The exception is the unit line, which scrolls horizontally and centres the current station.

## Elevation & Depth

Flat by default. Depth comes from a 1px border (`border`) or a 1px ring at 10% foreground (cards), and from tonal fills (Mist at 40 to 50%) for hand-off and banner surfaces. Buttons press down 1px when active instead of lifting.

### Shadow Vocabulary
- **Floating action** (`shadow-lg`): only the fixed phone "Ask the tutor" button, which floats above the reading column.

### Named Rules
**The Hairline Rule.** Separate with a hairline or with space, never with a shadow. The only shadow belongs to the one element that floats.

## Shapes

Gently rounded rectangles from one radius variable (`--radius` 0.625rem) and its multiples: controls (buttons, inputs, selects, list-row links) at 0.625rem, panels and cards at 0.875rem, small buttons at most 0.5rem, and the phone sheet's top corners at 1.125rem. Badges are pills, and station dots and avatars are circles. Borders are 1px hairlines. The two exceptions are 2px: the active-tab underline and the station dot's stroke. The station line's track is a 2px rule.

## Components

### Buttons
- **Shape:** gently rounded (0.625rem). Heights: 2rem default, 2.25rem `lg`, 1.75rem `sm`, 1.5rem `xs`.
- **Primary:** graphite fill with white text, 14px/500. A trailing arrow icon marks forward motion ("Check yourself →", "Next stop →").
- **Hover / Focus / Active:** the primary fades to 80%. Outline and ghost fill with Mist. Focus is a 3px Focus Grey ring at 50%. Active presses 1px down.
- **Pending:** a `pending` button shows a spinning loader before its label, sets `aria-busy` and is disabled, but stays at full colour (only truly disabled buttons fade to 50%). Use it for every in-flight mutation.
- **Outline / Secondary / Ghost / Link / Destructive:** steps down from the primary. Destructive is red text on a 10% red wash, never a solid red fill.

### Chips (Badges)
- **Style:** pill (1.625rem radius), 1.25rem tall, 12px/500. Variants: graphite (default), Mist (secondary), red wash (destructive) and hairline outline.
- **Use:** progress status beside the topic title, "Next stop" on the next station row, and "Optional" on setup steps.

### Cards / Containers
- **Card:** white with a 0.875rem radius, a 1px ring at 10% foreground and 1rem padding; the footer is Mist at 50% with a top hairline.
- **Panel (convention):** most surfaces are a plain `section` with a 0.875rem radius, a hairline border and 1.25rem padding, rather than a Card.
- **Lists:** rows separated by `divide-y` inside one bordered rounded box (dashboard courses), or between top and bottom hairlines (setup checklist).

### Inputs / Fields
- **Style:** transparent background, hairline stroke, 0.625rem radius, 2rem tall. Text is 16px on phones (which avoids iOS zoom) and 14px from `md` up. Textareas grow with their content from a 4rem minimum. Selects use the native `<select>` styled to match.
- **Focus:** the border turns Focus Grey, with a 3px ring at 50%.
- **Error / Disabled:** `aria-invalid` gives a red border and a 20% red ring; disabled fields fade to 50% over a 50% input fill.

### Navigation
- **Header:** the "Karaage" wordmark in 600 text on the left and the account menu on the right, over a bottom hairline.
- **Route tabs:** every tab is a link with its own URL, in a row over a bottom hairline. Tabs are 14px/500 with 0.625rem by 0.75rem padding. The current tab is Ink with a 2px Ink underline that overlaps the hairline; the others are Pencil with an Ink hover. Tabs wrap onto further lines on narrow screens, and a tab may carry a check icon or a tabular score.
- **Breadcrumb:** 14px Pencil text separated by `›`, with links that turn Ink and underline on hover.

### Station Line (signature)
- **Dot:** a 0.875rem circle with a 2px stroke and a 300ms ease-out transition (none with reduced motion). States: **done** is an Ink fill; **studied** is half Ink and half Paper (a left-to-right split); **revise** is an amber stroke over an amber-100 fill; **todo** is a hollow Paper fill with a Pencil stroke at 60%.
- **Next-stop ring:** a 2px Ink ring offset 2px from the dot. Exactly one station in a course carries it.
- **Unit line (session):** stations sit evenly along a horizontal 2px track (each at least 7rem wide), with 12px titles clamped to two lines. The current topic is 600 Ink with "You're here" beneath it, and the next stop carries "Next stop" beneath.
- **Unit stations (course home):** a vertical track in a 1.75rem gutter. Each row is a rounded link with a Mist hover, showing the title and, on the right, its metadata ("Completed · last check 90%"). The next stop's row adds a graphite "Next stop" badge and a 500 title.

### Next-Stop Panel (signature)
A bordered panel (0.875rem radius, 1.25rem padding) with a 1.125rem/500 "Next stop: <topic>" title, one or two lines of Pencil detail, and a single large primary link with a trailing arrow. It appears on the course home, as the dashboard's Continue panel, and as the outcome panel after a check. The revise outcome uses the amber border and wash.

### Setup Checklist
An ordered list between hairlines. Each step has a 20px state icon in a 1.75rem gutter (check for done, dot for current, spinner for running, dashed circle for waiting, plain circle for optional), a 500 title, a one-line Pencil summary and an "Open" or "Change" ghost button. Only the current step is expanded. When every required step is done, the list collapses into a one-line bordered summary with a "Show setup" link.
- **No step blocks on an optional one.** Study materials are optional and accept any type. "Units and topics" always has an action: read them from any file already in the workspace (whichever course it was uploaded under), or type them in. "Waiting" is reserved for real dependencies, such as lessons waiting on topics.

## Do's and Don'ts

### Do:
- **Do** give each view exactly one filled primary action, and step every other action down to outline, ghost or link.
- **Do** separate with hairlines (`border`) and space; reserve the 10% foreground ring for Card.
- **Do** use the `pending` button state for in-flight requests instead of disabling and fading the button.
- **Do** express topic progress with StationDot states and name the course's one next stop with its ring and a "Next stop" badge.
- **Do** cap reading text at 65ch and use `tabular-nums` for counts and scores.
- **Do** make tabs that change content into links (RouteTabs), so back, reload and sharing land on the same tab.

### Don't:
- **Don't** use amber for anything except revise states.
- **Don't** add shadows to static surfaces; the only shadow belongs to the floating phone tutor button.
- **Don't** set labels in uppercase or with wide letter-spacing; the build has none.
- **Don't** introduce a second typeface or a brand hue; the primary is graphite.
- **Don't** show more than one "next" destination on a screen.
