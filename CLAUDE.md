# Waypoints — AI tutoring and planning app

A chart that plans a route through a field (what's achieved, what's
realistically next, what's a long shot — a reference map, not a strict linear
progression) plus a one-to-one AI teacher (Learning mode) that takes the
learner along it.

**Direction (2026-10-02):** the app began as a personal life-progress tracker
with five domains. At the user's request the Career, Health & Fitness,
Finance and Skills & Hobbies tabs were removed; **Programming is the only
field now**, and the longer-term aim is a full-stack tutoring and planning app
for any field. Nothing field-general has been built yet (teacher prompts and
the practice runner are still programming/Python-specific) — don't build
"create a field" or rename prompts to be field-neutral unless asked.

The code is public at https://github.com/ShxZai/waypoints (MIT). `data/`,
`notes/`, `.env`, `waypoints.html`, the career files and the third-party
`learn-main/` / `Manware-…` folders are git-ignored; keep it that way.

## Status

Now a **local web app** (Python/FastAPI backend + the Waypoints page),
started with `run.bat` and opened at http://127.0.0.1:8000. It began as a
Claude Artifact; the user moved it local so Learning mode's teacher can
research the web, run real Python, and save notes as files — none of which
the artifact sandbox allows.

- **Edit `web/index.html`** (the page) and `app/` (the backend) from now on.
  `web/index.html` was generated from `waypoints.html` by swapping only the
  platform seams (storage, teacher, Python runner, code editor, notes).
- `waypoints.html` is the **artifact snapshot**, still published at
  https://claude.ai/artifact/UehrDGJrkNGak43igTJZbL (v13). It is no longer
  kept in sync; only republish it if the user asks.

## Local app (how it's built)

- `run.bat` — first run creates `.venv`, installs `requirements.txt`,
  copies `.env.example` to `.env`; then starts uvicorn on 127.0.0.1:8000.
- `web/local-runtime.js` — provides the artifact-era `window.claude.use()`
  interface (`db`, `sample`, `downloads`) backed by the server, plus
  `window.waypointsLocal` (status, usage limits, real Python, notes). This
  is why the Learning-mode code barely changed.
- `app/main.py` — `/api/docs/{collection}[/{id}]` (SQLite JSON docs,
  `data/waypoints.db`), `/api/ask` (teacher, NDJSON stream of `delta` /
  `done` / `error` events), `/api/run` (real CPython via `app/runner.py`:
  temp dir, `-I`, 10 s timeout, output cap), `/api/notes/{name}` (session
  logs as `notes/<nid>-learning-log.md`, Obsidian-style callouts, written on
  every log save), `/api/status`, `/api/limits`. Security: Host must be
  127.0.0.1/localhost:8000 and every non-GET needs `X-Waypoints: 1` (the
  API can run code, so other websites must not be able to call it).
- **Teacher switch** (`TEACHER` in `.env`), both behind `app/teacher/base.py`:
  - `claude_code` (default, the user's choice): the user's **Claude
    subscription (Pro)** via `claude -p` — `--system-prompt`, `--json-schema`
    (answer in `structured_output`), `--output-format stream-json
    --include-partial-messages --verbose`, `--tools ""` (research calls:
    `--tools WebSearch WebFetch` + `--allowedTools`), `--model` / `--effort`
    per tier (quick/default = sonnet, complex = opus with
    `--fallback-model sonnet`), `--no-session-persistence`, run in an empty
    temp dir. Never `--bare` (API-key-only). Rate-limit events feed the
    rail's "Claude usage" line. Measured: probe round ~25-40 s, plan (Opus
    5.5) ~60 s, web research ~80 s, chat first words ~1.5 s.
  - `api`: Anthropic API key (pay per use), official SDK 1.x, streaming,
    structured outputs (`output_config.format`, falls back to parsing),
    prompt caching, `web_search_20260209` / `web_fetch_20260209`,
    `pause_turn` resume, per-session cost estimate.
- JSON tasks send a JSON Schema (`SCHEMAS` in the page: probe, plan, step,
  remed, ex, lab); `makeQuiz()` / `validatePlan()` still re-check content.
  Quizzes have exactly one correct answer (keeps schemas simple).
- Code editor: CodeMirror 5 (Python mode) replaces `textarea.code-editor`,
  themed from the page tokens; focus/cursor survive background re-renders.
- Tests (standard library only, no teacher calls, never touch `data/` or
  `notes/`): `.venv\Scripts\python -m unittest discover tests` starts the
  server on a spare port with a temp DB/notes folder and checks docs,
  `/api/run` (output, errors, timeout, output cap), the Host/`X-Waypoints`
  guards, notes and the page. `node tests/check_learn_seeds.js
  .venv/Scripts/python.exe` checks every Learning-mode seed (strand range,
  unique options, one correct answer, and `verify:"output"` keys run
  against CPython).

## Concept / design decisions

- **Metaphor**: a navigation chart ("Waypoints") — night-sky star chart in
  dark theme, day trail-map in light theme. Deliberately chosen over a generic
  "tech tree" look.
- **Not a strict ladder**: each domain is a small graph with multiple parallel
  lanes/branches (e.g. Career splits into Employment / Leadership /
  Independent lanes), not one single chain. Nodes have prerequisite edges but
  the user can mark any node achieved out of order — the chart is a reference,
  not a hard gate. This was an explicit user requirement.
- **Status model per node**: `locked` (not yet reachable) → `available` (open
  next) → `active` (in progress) → `done` (achieved). Locked nodes
  auto-promote to available once a prerequisite is done; user can always
  override manually regardless of lock state.
- **"Long shot" flag**: separate boolean per node, user-toggleable,
  independent of status. This is the "index of what's less likely achievable
  for me" the user asked for — shown as a dashed ring around the node. It's a
  personal judgment call, not derived from the data.
- **One domain: Programming** (30 nodes across 6 lanes — Foundations, Math &
  Classical ML, Deep Learning, Systems & Infra, Projects & Portfolio,
  Research & Theory — a concrete Python-to-frontier-AI-lab progression the
  user asked for by name). `DOMAINS` is still an array and the tab bar,
  counters and persistence still loop over it, so a second field is a data
  addition. The four generic template domains (Career, Health & Fitness,
  Finance, Skills & Hobbies; ids c*/h*/f*/s*) were removed on 2026-10-02;
  their old entries in a saved `chart/state` doc are ignored on load. Older
  notes below that say "the other four domains" refer to them.
- **Research & Theory lane (pg26-pg30)**: added after a conversation about
  whether math-specialized ML/AI research roles exist (they do — theory/
  interpretability research at labs like Anthropic) and whether that
  progression belonged in the chart. It branches off Math & Classical ML
  (pg6 linear algebra/calc + pg7 probability/stats) rather than being a new
  domain, since it's a depth specialization of the existing math track, not
  a separate career: Mathematical foundations for ML theory → Statistical
  learning theory → Optimization & loss landscape theory → Information
  theory & representation geometry → a stretch capstone (original
  theoretical/interpretability result), the same "gate all deps through a
  chain, cross-lane prereqs where a lane genuinely depends on another
  lane's node" pattern already used by Systems & Infra. Like pg1-pg25,
  pg26-pg30 now have full `WAYPOINTS_RESOURCES` entries (29 items total) —
  sourced by five parallel fork agents (one per node) that each did live
  web search and link verification, same bar as the original 25 nodes:
  MIT OCW, Stanford EE364A (Boyd), 3Blue1Brown, Shalev-Shwartz & Ben-David's
  free ML-theory textbook, Anthropic's Transformer Circuits Thread
  (transformer-circuits.pub) for the interpretability items, MacKay's free
  information theory book, and similar primary/high-quality sources — a
  couple of items intentionally have no video or no practice link where no
  good one existed, same convention as the original data.
- **Per-node skill checklist**: a node can optionally carry a `checklist:
  [string, ...]` array — concrete, checkable sub-skills for a broad node
  (e.g. "Data structures & algorithms"). When present, selecting the node
  shows checkboxes + a mini progress bar in the panel; checking everything
  surfaces a soft hint suggesting the node be marked achieved, but doesn't
  force it (same reference-not-a-gate philosophy as status/prereqs).
  Currently only populated for the Programming domain's 25 nodes — the other
  four domains have no `checklist` field, so the section simply doesn't
  render for them. Checklist state resets on reload same as everything else.
- **Per-checklist-item mastery resources**: each of the Programming domain's
  ~129 checklist items (across all 25 nodes) can carry a resource bundle —
  a short explainer, a video, a course/docs link, 0-3 practice-problem links,
  and a hard "mastery challenge" project scoped to just that one sub-skill.
  Data lives in its own `window.WAYPOINTS_RESOURCES` script block (kept
  separate from the `DOMAINS` app data/logic block, both still in the same
  single HTML file) keyed by node id, item-index-aligned with that node's
  `checklist` array. An "Expand ⤢" button on the checklist section opens a
  full-screen modal rendering every item with its resources visible at once
  (vs. the cramped 300px side panel). All ~300 resource links were sourced
  via live web search (not guessed) and link-checked; a handful of items
  intentionally have no video/course/practice where no good real resource
  existed — the UI just omits that field rather than showing a fake one.
  Only Programming has this data so far; the other four domains have no
  checklists to attach resources to in the first place.
- **Three-tier checklist split — Foundational / Advanced / Recall & practice
  (optional)**: each Programming node's `checklist` array carries two
  parallel index arrays: `coreChecklist: [i, j, ...]` (0-based indices of
  items worth genuinely learning — "judgment/understanding") and
  `advancedChecklist: [i, ...]`, a subset of `coreChecklist` marking which
  of those core items are the deeper/later ones ("Advanced") rather than
  the first mental model to build ("Foundational"). Items in `checklist`
  but *not* in `coreChecklist` render under "Recall & practice — optional."
  The classification axis is explicitly about the AI-assisted-engineer era:
  items that build real judgment/debugging ability (foundational or
  advanced) are kept, while items that are pure syntax recall, tool/process
  mechanics, or volume-of-repetition ("solved 100+ problems," "comfortable
  with *args/**kwargs") are optional, on the reasoning that an AI copilot
  will handle recall-shaped work but can't substitute for the judgment
  needed to review/debug what it produces. This came from an explicit user
  conversation about what's actually worth learning given they'll mostly
  use AI to write code — not a rule, a hand-classified judgment call per
  item, same spirit as the `stretch` flag, so expect to keep hand-tuning it.
  Indices (not a leading count) were used deliberately so tiers don't have
  to be contiguous in the array — this keeps `WAYPOINTS_RESOURCES`'
  index-alignment with `checklist` completely untouched (no reordering).
  Mechanically, `coreChecklist` (foundational + advanced combined) is still
  the single gate for "minimum to progress": the progress bar/checkbox fill
  color switches from accent-2 (blue) to good (green) once every core item
  is checked, regardless of the foundational/advanced sub-split — that
  split is a display/sequencing aid, not a second, stricter gate. The UI
  renders three labeled groups per node (only groups with >0 items render;
  e.g. a node with an empty `advancedChecklist` just shows two groups), a
  status line ("x/y core (judgment) items checked"), and a hint once core
  is met but the optional group isn't ("core judgment items done — the
  rest is optional recall/practice").
- **Custom checkbox styling**: all checkboxes in the app (skill checklist,
  expanded modal, and the "personal long shot" toggle) are styled via a
  shared `.wp-check` class (`appearance: none` + themed border/fill/check
  mark) instead of native OS checkboxes, so they follow the light/dark
  design tokens. Modifier classes: `.wp-core` (accent-2 fill, used for
  minimum-to-progress items), plain `.wp-check` (good/green fill, used for
  full-mastery items), `.wp-stretch` (stretch/purple fill, long-shot
  toggle), and `.wp-lg` (slightly larger, used in the expanded modal where
  item text is bigger). The expanded modal's scrollbar (and its backdrop)
  also got themed `scrollbar-color`/`::-webkit-scrollbar-*` rules matching
  the existing `.chart-frame` scrollbar treatment, rather than leaving the
  OS-default scrollbar in the modal.

- **Learning mode (pg1, pg2, pg3, pg6, pg7 — see `LEARN_NODES`)**: a
  "Learning mode" tab (right end of the tab bar; also a "Study this in
  Learning mode →" button in the panel for those nodes) turns the chart into a one-to-one teacher, at the
  user's request for "one consistent source" instead of hopping between
  websites. **Its structure and philosophy come from `learn-main/`** (a
  personal AI-learning system the user took inspiration from, built for
  pi; read `learn-main/learn-main/skills/teach/SKILL.md` before changing
  teaching behavior). Carried over: the goal is understanding (a dependency
  graph of connected facts), via Principle i "unconditional truths first"
  and Principle ii "how could I have discovered this?", Socratic vs
  expository per node, accuracy over flow. The three phases, run per
  checklist node:
  1. **Probe** — a goal question (no right answer, like `ask_user_question`)
     then graded quizzes (like `quiz.ts`: shuffled options, always an
     "I don't know", optional note, explanation after answering). Opens with
     hand-written seed questions (`WAYPOINTS_LEARN[nid].seeds`, one per
     strand = checklist item; output answer keys verified against CPython),
     then Claude generates adaptive rounds (≤3 questions) until every
     goal-relevant strand is *bracketed* (a floor they got right + a ceiling
     they missed), shown live as a per-strand "map of your edge".
  2. **Plan** — Claude (complex tier) draws a dependency map: unconditional
     truths (diamonds) → derived steps (circles) → the learner's goal
     (ringed), with already-held foundations as `known` nodes. Rendered in
     the chart's own SVG style; learner approves or sends feedback to
     revise before any teaching.
  3. **Teach** — per map node in topological order: motivate → (Socratic:
     a "discover" quiz before the reveal) → establish → connect → 1-2 quiz
     checks; a miss triggers a diagnosed re-teach + fresh checks (max 3),
     then "move on anyway". The next node is prefetched while the learner
     works.
  **Figure maker** (added 2026-10-02; the *idea* of learn-main's
  `svg-maker`, deliberately not a copy — no pi tools, PNGs or Obsidian
  vault): for positions-and-shapes ideas the lesson teacher writes a
  ```figure fence (first line `caption:`, then a brief); Mermaid stays for
  nodes-and-edges. `makeFigures()` then makes a separate maker call
  (`FIGURE_RULES`, plain `sample()`), `checkFigure()` sanitizes the SVG
  (DOMPurify SVG profile) and measures it in the browser (labels cut off,
  overlapping, too small, too many elements), one repair call if needed,
  otherwise the figure is left out. Stored as `steps/<key>.figs[]`
  (`{brief, state: ok|none|failed, svg}`), rendered by `enhanceProse` as
  `<figure class="fig">`; colours only through the `.fig` classes (`box`,
  `line`, `head`, `accent`, `good`, `warn`, `dim`, `small`, `mono`) so they
  follow the theme. Lessons and re-teaches only (not chat, not old
  lessons); the notes file keeps just the caption. The checks catch layout
  faults, not whether the picture is semantically right.
  **Teacher chat panel** (added 2026-10-02 at the user's request, replacing
  the collapsed "Ask about this node" box): a sticky third column
  (`#learnChat`, `chatThread()` / `chatPanelHtml()`), one thread per lesson
  (`steps/<key>.chat`), per practice skill (`units/<key>.chat`) and per lab
  (`learn/<nid>.labChat`); hidden on probe/plan/log so probe answers aren't
  coached. The teacher is given the lesson, its quizzes and the learner's
  answers (answer keys of unanswered quizzes are withheld via
  `quizSummary(c, true)`), re-teaches, exercise code/output, lab code.
  Selecting text or code in the pane shows an "Ask about this" button
  (`#askSel`) that quotes it into the chat box. "Hide" collapses it to a
  floating button (remembered in `localStorage`); with the chat open on wide
  screens `.learn.chat-on` grows wider than the page column.
  Then **Practice** (3 exercises per strand with assert tests, run in real
  Python, code review) and a **Lab**. Subagent roles became separate calls:
  a one-time "field survey" per node (the researcher's role, now with real
  web search and a Sources section) feeds probe distractors, plan and
  lessons; quiz questions marked `verify:"output"` are run in real Python
  and discarded if the printed output doesn't match the key (the "verify by
  looking" idea). Mermaid fences in lessons are lazy-rendered and dropped if
  they don't parse ("a missing visual beats a wrong one"); python fences get
  a Run button. A session log (md-log equivalent) records every
  question/answer/lesson, is saved to `notes/` automatically, and can be
  exported. The shared prompt blocks are `PHILOSOPHY`, `STYLE`,
  `QUIZ_RULES`, `PROBE_RULES`. `STYLE` also carries readability rules
  added 2026-10-01 after the user reviewed the pg1/pg2 lessons: define a
  field-level concept before using it, write abbreviations out the first
  time (BFS, BST…), introduce every code block, comment teaching code (but
  not quiz code), end with what the idea is used for plus an example, and
  never show internal map ids (n1, n2…) to the learner. Persistence: collections `learn/<nid>`,
  `steps/<nid>-<mapNodeId>`, `units/<nid>-<i>` (practice), `scope/<nid>`,
  `logs/<nid>`. Extending to more nodes = add the id to `LEARN_NODES` and a
  `goal` + `seeds` entry to `WAYPOINTS_LEARN`, then run
  `node tests/check_learn_seeds.js .venv/Scripts/python.exe`. pg3/pg6/pg7
  were added on 2026-09-26. pg4 (C/C++) and pg5 (interviews) were
  deliberately left out, and so were the scikit-learn/PyTorch nodes: the
  teacher's `STYLE` and practice runner assume standard-library Python 3.12
  (the venv has no numpy/torch/C compiler), so those nodes need a design
  decision first (another language/runner, or extra packages).
- **Persistence note**: checklist ticks (`checklist/<nid>`), chart node
  status + long-shot flags (one doc, `chart/state`, all domains — added
  2026-09-29 at the user's request) and Learning-mode progress persist
  (SQLite in the local app). On load, unknown node ids / invalid statuses
  are ignored and `recalcUnlocks()` runs, so edits to the node data don't
  break saved state.

## Next steps (not started)

1. Towards "any field": Learning mode for the remaining Programming nodes
   (needs a runner/packages decision, see the Learning mode notes), then
   charts and non-code practice for other fields. Only when asked.
2. Optional later: put the app online privately (needs `TEACHER=api`, a host,
   and a login). Only if asked.
3. Possible future additions the user has *not* asked for yet (don't build
   unprompted): journaling/notes per node, dates achieved, editing the graph
   structure itself (add/remove nodes) from the UI.

## Working notes for future sessions

- Vanilla HTML/CSS/JS in one file by design (fast iteration, no build step).
  Keep it that way unless the user explicitly asks to turn this into a real
  app project.
- Design tokens (colors/fonts) are defined at the top of `waypoints.html`
  under `:root` — light theme is the base, dark theme is layered via
  `prefers-color-scheme` and `[data-theme]`. Follow the existing token
  pattern rather than hardcoding new colors if extending the UI.
