# B.O.B UI Plan

> Design specification for B.O.B's local-first web interface.

**Last Updated:** 2025-12-23  
**Status:** Implemented (Phase 3 Complete)  
**Version:** 1.0.0

---

## Table of Contents

1. [Product Goals](#product-goals)
2. [UX Principles](#ux-principles)
3. [Core Screens](#core-screens)
4. [Required UI Behaviors](#required-ui-behaviors)
5. [Component List](#component-list)
6. [Page Routes](#page-routes)
7. [Wireframes](#wireframes)
8. [Acceptance Criteria](#acceptance-criteria)
9. [Test Plan](#test-plan)

---

## Product Goals

### Primary Goal

Provide a **beautiful, trustworthy interface** for asking questions and exploring knowledge, where every answer is transparently grounded in the user's own documents.

### Success Metrics

1. **Zero hallucinations visible**: Every claim links to a verifiable source
2. **Instant source inspection**: One click from answer to original document
3. **Full transparency**: Date confidence and freshness warnings always shown
4. **Works offline**: No network requests to external services
5. **Fast startup**: UI usable within 2 seconds of `bob serve`

### Non-Goals

- Complex rich text editing
- Real-time collaboration
- Cloud sync or sharing
- Mobile-first design (desktop-first, mobile-acceptable)

---

## UX Principles

### 1. Citations First

Every answer must immediately show its sources. The sources are not an afterthought—they are the proof that makes the answer trustworthy.

**Implementation:**

- Sources panel visible alongside every answer
- Source numbers inline in answer text: `[1]`, `[2]`
- Each source is a clickable link to the original

### 2. Inspectable Sources

Users must be able to verify any claim by viewing the original context with minimal friction.

**Implementation:**

- Click source → opens file at exact locator
- Hover source → preview snippet
- If file can't be opened → show path + manual instructions

### 3. Transparent Confidence

Users must always know how fresh and reliable the information is.

**Implementation:**

- Date confidence badge on every result (HIGH/MEDIUM/LOW)
- "This may be outdated" warning on stale content
- Source dates visible in the sources list

### 4. Fail Gracefully

When the system cannot answer, it must be explicit rather than making things up.

**Implementation:**

- "Not found in sources" displayed prominently
- Suggestions for how to add relevant content
- Never show empty state without explanation

### 5. Local and Fast

Everything runs on the user's machine. No spinners waiting for cloud services.

**Implementation:**

- All assets bundled with server
- No external CDN or font loading
- Optimistic UI updates where possible

---

## Core Screens

### 1. Ask (Primary Screen)

The main interface for querying knowledge.

**Layout: 3-Pane**

```
┌─────────────────────────────────────────────────────────────────┐
│  B.O.B                                    [Library] [Indexing]  │
├──────────────┬──────────────────────────────┬───────────────────┤
│              │                              │                   │
│  FILTERS     │  QUERY + ANSWER              │  SOURCES          │
│              │                              │                   │
│  Projects:   │  ┌────────────────────────┐  │  1. doc.md        │
│  ☑ all       │  │ How do I configure...  │  │     heading: X    │
│  ☑ docs      │  └────────────────────────┘  │     HIGH | 2025   │
│  ☐ recipes   │                              │     [Open]        │
│              │  Answer:                     │                   │
│  Type:       │  To configure logging [1],   │  2. notes.md      │
│  ☑ markdown  │  add the following to your   │     heading: Y    │
│  ☑ pdf       │  config file...             │     MED | 2023    │
│              │                              │     ⚠️ May be old  │
│  Date:       │  ─────────────────────────   │     [Open]        │
│  After: ___  │  📋 Sources                  │                   │
│              │  📅 HIGH | Dec 2025          │                   │
│              │  ⚠️ None outdated            │                   │
│              │                              │                   │
└──────────────┴──────────────────────────────┴───────────────────┘
```

**Elements:**

- **Filter Sidebar (Left)**

  - Project multi-select
  - Document type filter
  - Date range filter
  - Language filter (if multilingual)

- **Query + Answer (Center)**

  - Large query input with submit button
  - Answer text with inline citation markers
  - Mandatory footer: Sources count, Date confidence, Outdated warning

- **Sources Panel (Right)**
  - Numbered source cards
  - Each card shows: filename, locator (heading/page/line), date, confidence
  - "Open" button to jump to source
  - Outdated warning badge if applicable

### 2. Library / Browse

Browse and manage indexed documents.

**Layout: List + Detail**

```
┌─────────────────────────────────────────────────────────────────┐
│  B.O.B > Library                          [Ask] [Indexing]      │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│  FILTERS     │  DOCUMENT LIST                                   │
│              │                                                  │
│  Project:    │  ┌─────────────────────────────────────────────┐ │
│  [All ▼]     │  │ 📄 architecture.md                          │ │
│              │  │    Project: docs | 15 chunks | Dec 2025     │ │
│  Type:       │  │    Last indexed: 2025-12-23                 │ │
│  [All ▼]     │  └─────────────────────────────────────────────┘ │
│              │  ┌─────────────────────────────────────────────┐ │
│  Sort:       │  │ 📕 manual.pdf                               │ │
│  [Date ▼]    │  │    Project: docs | 42 chunks | Nov 2025     │ │
│              │  │    Last indexed: 2025-12-20                 │ │
│  Search:     │  └─────────────────────────────────────────────┘ │
│  [________]  │  ┌─────────────────────────────────────────────┐ │
│              │  │ 📝 meeting-notes.md                         │ │
│              │  │    Project: work | 8 chunks | Oct 2025      │ │
│              │  │    ⚠️ May be outdated                       │ │
│              │  └─────────────────────────────────────────────┘ │
│              │                                                  │
│              │  Showing 45 of 156 documents                     │
│              │  [Load More]                                     │
│              │                                                  │
└──────────────┴──────────────────────────────────────────────────┘
```

**Elements:**

- Document cards with metadata
- Click to expand and see chunks
- Re-index button per document
- Delete from index option

### 3. Decisions View

View extracted decisions with status and provenance.

**Layout: Table + Detail**

```
┌─────────────────────────────────────────────────────────────────┐
│  B.O.B > Decisions                        [Ask] [Library]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FILTERS: [Active ▼] [All Projects ▼]     [Search decisions...] │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ✅ ACTIVE | DEC-001                              Dec 2025   ││
│  │ Use SQLite for all local storage                            ││
│  │ Source: architecture.md > "Database Choice"                 ││
│  │ [View Context] [View Source]                                ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🔄 SUPERSEDED | DEC-002                          Nov 2023   ││
│  │ Use PostgreSQL for storage                                  ││
│  │ Superseded by: DEC-001                                      ││
│  │ Source: old-decisions.md > "Initial DB"                     ││
│  │ [View Context] [View Source]                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Elements:**

- Status badges: Active (green), Superseded (yellow), Deprecated (gray)
- Decision text and context
- Link to superseding decision
- Click to view original source

### 4. Recipes View

Display structured recipe data (if present).

**Layout: Card Grid**

```
┌─────────────────────────────────────────────────────────────────┐
│  B.O.B > Recipes                          [Ask] [Library]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FILTERS: [All ▼]                         [Search recipes...]   │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ 🍝 Pasta        │  │ 🥗 Salad        │  │ 🍰 Cake         │  │
│  │ Carbonara       │  │ Caesar          │  │ Chocolate       │  │
│  │                 │  │                 │  │                 │  │
│  │ 30 min | Easy   │  │ 15 min | Easy   │  │ 2 hr | Medium   │  │
│  │ 4 servings      │  │ 2 servings      │  │ 8 servings      │  │
│  │                 │  │                 │  │                 │  │
│  │ [View Recipe]   │  │ [View Recipe]   │  │ [View Recipe]   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Recipe Detail:**

- Title and description
- Ingredients list
- Instructions (numbered)
- Source citation and date
- "Open Original" button

### 5. Indexing Dashboard

Monitor and trigger indexing jobs.

**Layout: Actions + Progress + History**

```
┌─────────────────────────────────────────────────────────────────┐
│  B.O.B > Indexing                         [Ask] [Library]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INDEX NEW CONTENT                                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Path: [/Users/me/Documents/notes_______________] [Browse]  ││
│  │  Project: [notes_____________▼]                             ││
│  │                                                             ││
│  │  [Start Indexing]                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  CURRENT JOB                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  📂 /Users/me/Documents/notes                               ││
│  │  Progress: ████████████░░░░░░░░ 60% (45/75 files)           ││
│  │  Status: Processing meeting-notes-dec.md                    ││
│  │  Elapsed: 00:45                                             ││
│  │                                                             ││
│  │  [Cancel]                                                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  RECENT JOBS                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  ✅ /Users/me/docs     | 2025-12-23 10:30 | 156 files       ││
│  │  ✅ /Users/me/recipes  | 2025-12-22 14:15 | 23 files        ││
│  │  ❌ /Users/me/broken   | 2025-12-21 09:00 | 2 errors        ││
│  │     └─ View Errors                                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Elements:**

- Path input with folder browser (if supported)
- Project selector
- Real-time progress bar
- File-by-file status
- Error log for failed files
- Job history

---

## Required UI Behaviors

### 1. Click-to-Open Source

When user clicks a source citation:

1. Send `POST /open` with file path and locator
2. If successful: file opens in default editor at location
3. If failed: display toast with path + locator for manual access

**Locator Handling by Type:**

| Source Type | Locator Display            | Open Behavior                |
| ----------- | -------------------------- | ---------------------------- |
| Markdown    | "heading: X (lines 45-67)" | Open file, scroll to line 45 |
| PDF         | "page 12 of 34"            | Open file at page 12         |
| Word        | "paragraph 5 in 'Section'" | Open file (best effort)      |
| Excel       | "sheet: Data, 100 rows"    | Open file, activate sheet    |
| Git/Code    | "src/app.py lines 10-25"   | Open file at line 10         |

### 2. Answer Footer (Mandatory)

Every answer display MUST include:

```
─────────────────────────────────────────
📋 Sources: 3 documents cited
📅 Date Confidence: HIGH
⚠️ This may be outdated: 1 source is >6 months old
─────────────────────────────────────────
```

**Rules:**

- If 0 sources: show "Not found in sources. Try adding relevant documents."
- Date confidence: HIGH (all <3 months), MEDIUM (some 3-6 months), LOW (any >6 months)
- Outdated warning: show if ANY source >6 months old

### 3. "Not Found" Handling

When query returns no relevant results:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ⚠️ Not found in sources                                       │
│                                                                 │
│  No indexed documents contain information about your query.     │
│                                                                 │
│  Suggestions:                                                   │
│  • Check if relevant documents are indexed (Library view)       │
│  • Try different keywords or phrasing                           │
│  • Index additional content (Indexing view)                     │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  📋 Sources: 0 documents                                        │
│  📅 Date Confidence: N/A                                        │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Indexing Progress

During active indexing job:

- Poll `GET /index/{job_id}` every 2 seconds
- Update progress bar and current file
- Show error count incrementally
- On completion: toast notification + refresh library

### 5. Keyboard Shortcuts

| Shortcut    | Action                    |
| ----------- | ------------------------- |
| `/`         | Focus query input         |
| `Cmd+Enter` | Submit query              |
| `Escape`    | Clear query / close modal |
| `1-9`       | Open source 1-9           |
| `Cmd+K`     | Quick navigation          |

---

## Component List

### Layout Components

| Component   | Description                           | Used In      |
| ----------- | ------------------------------------- | ------------ |
| `AppShell`  | Main layout with nav and content area | All pages    |
| `NavBar`    | Top navigation with page links        | All pages    |
| `Sidebar`   | Collapsible filter sidebar            | Ask, Library |
| `ThreePane` | 3-column layout container             | Ask          |

### Content Components

| Component       | Description                              | Used In   |
| --------------- | ---------------------------------------- | --------- |
| `QueryInput`    | Search input with submit                 | Ask       |
| `AnswerDisplay` | Answer text with citation markers        | Ask       |
| `AnswerFooter`  | Sources count, date confidence, warnings | Ask       |
| `SourceCard`    | Individual source with metadata + open   | Ask       |
| `SourceList`    | Scrollable list of SourceCards           | Ask       |
| `DocumentCard`  | Document summary in library              | Library   |
| `DecisionRow`   | Single decision with status              | Decisions |
| `RecipeCard`    | Recipe preview card                      | Recipes   |
| `ProgressBar`   | Job progress indicator                   | Indexing  |
| `JobHistory`    | List of past indexing jobs               | Indexing  |
| `ErrorLog`      | Expandable error details                 | Indexing  |

### UI Components

| Component    | Description                 | Used In  |
| ------------ | --------------------------- | -------- |
| `Badge`      | Status/confidence indicator | Multiple |
| `Button`     | Primary/secondary actions   | Multiple |
| `Dropdown`   | Select with options         | Filters  |
| `Checkbox`   | Multi-select filters        | Filters  |
| `DatePicker` | Date range selection        | Filters  |
| `Toast`      | Notification messages       | Multiple |
| `Modal`      | Dialog overlay              | Details  |
| `Tooltip`    | Hover information           | Multiple |

---

## Page Routes

| Route          | Component       | Description               |
| -------------- | --------------- | ------------------------- |
| `/`            | `AskPage`       | Main query interface      |
| `/library`     | `LibraryPage`   | Browse indexed documents  |
| `/library/:id` | `DocumentPage`  | Single document details   |
| `/decisions`   | `DecisionsPage` | List extracted decisions  |
| `/recipes`     | `RecipesPage`   | Browse structured recipes |
| `/recipes/:id` | `RecipePage`    | Single recipe details     |
| `/indexing`    | `IndexingPage`  | Indexing dashboard        |

**Note:** All routes are client-side. The server serves `index.html` for all paths and JS handles routing.

---

## Wireframes

### Ask Page - Query State

```
+------------------+--------------------------------+------------------+
|                  |                                |                  |
|  [B.O.B Logo]    |  ┌──────────────────────────┐  |  SOURCES         |
|                  |  │ [Query input...        ] │  |                  |
|  ══════════════  |  └──────────────────────────┘  |  (empty)         |
|                  |                                |                  |
|  PROJECTS        |  Recent queries:               |  Enter a query   |
|  ☑ All (156)     |  • "How to configure..."      |  to see sources  |
|  ☐ docs (45)     |  • "What decisions about..."  |                  |
|  ☐ recipes (23)  |  • "Recipe for..."            |                  |
|  ☐ work (88)     |                                |                  |
|                  |                                |                  |
|  ══════════════  |                                |                  |
|                  |                                |                  |
|  DOCUMENT TYPE   |                                |                  |
|  ☑ All           |                                |                  |
|  ☐ Markdown      |                                |                  |
|  ☐ PDF           |                                |                  |
|                  |                                |                  |
+------------------+--------------------------------+------------------+
```

### Ask Page - Answer State

```
+------------------+--------------------------------+------------------+
|                  |                                |                  |
|  [B.O.B Logo]    |  ┌──────────────────────────┐  |  SOURCES         |
|                  |  │ How do I configure X?    │  |                  |
|  ══════════════  |  └──────────────────────────┘  |  ┌────────────┐  |
|                  |                                |  │ 1. doc.md  │  |
|  PROJECTS        |  ANSWER                        |  │ heading: X │  |
|  ☑ All (156)     |  ─────────────────────────     |  │ HIGH       │  |
|  ☐ docs (45)     |  To configure X [1], you       |  │ Dec 2025   │  |
|  ☐ recipes (23)  |  need to edit the config       |  │ [Open]     │  |
|  ☐ work (88)     |  file [2]. The key setting     |  └────────────┘  |
|                  |  is `foo.bar` which controls   |  ┌────────────┐  |
|  ══════════════  |  the behavior of...            |  │ 2. cfg.md  │  |
|                  |                                |  │ lines 5-20 │  |
|  DOCUMENT TYPE   |  ─────────────────────────     |  │ MEDIUM     │  |
|  ☑ All           |  📋 2 sources                  |  │ Jun 2025   │  |
|  ☐ Markdown      |  📅 MEDIUM confidence          |  │ ⚠️ Old     │  |
|  ☐ PDF           |  ⚠️ 1 source may be outdated   |  │ [Open]     │  |
|                  |                                |  └────────────┘  |
+------------------+--------------------------------+------------------+
```

### Indexing Page - Active Job

```
+--------------------------------------------------------------------+
|  [B.O.B] > Indexing                            [Ask] [Library]     |
+--------------------------------------------------------------------+
|                                                                    |
|  INDEX NEW CONTENT                                                 |
|  ┌────────────────────────────────────────────────────────────┐    |
|  │ Path: [/path/to/folder_________________] [Browse]          │    |
|  │ Project: [my-project ▼]                [Start Indexing]    │    |
|  └────────────────────────────────────────────────────────────┘    |
|                                                                    |
|  ┌────────────────────────────────────────────────────────────┐    |
|  │  📂 CURRENT JOB: /path/to/folder                           │    |
|  │  ══════════════════════════════════════════════════════    │    |
|  │                                                            │    |
|  │  Progress: ████████████████░░░░░░░░░░░░░░░░ 45%            │    |
|  │  Files: 34 / 75 processed                                  │    |
|  │  Current: processing architecture.md                       │    |
|  │  Elapsed: 00:01:23                                         │    |
|  │                                                            │    |
|  │  Errors: 2                                                 │    |
|  │  • corrupt.pdf - Failed to parse PDF                       │    |
|  │  • empty.md - No content extracted                         │    |
|  │                                                            │    |
|  │  [Cancel Job]                                              │    |
|  └────────────────────────────────────────────────────────────┘    |
|                                                                    |
|  RECENT JOBS                                                       |
|  ┌────────────────────────────────────────────────────────────┐    |
|  │ ✅ 2025-12-23 10:30 | /docs     | 156 files | 0 errors    │    |
|  │ ✅ 2025-12-22 14:15 | /recipes  | 23 files  | 0 errors    │    |
|  │ ⚠️ 2025-12-21 09:00 | /broken   | 45 files  | 3 errors    │    |
|  └────────────────────────────────────────────────────────────┘    |
|                                                                    |
+--------------------------------------------------------------------+
```

---

## Acceptance Criteria

### Phase 3 Acceptance (UI Ships)

These criteria must pass for Phase 3 to be complete:

| ID    | Criterion                                                   | Test Method      |
| ----- | ----------------------------------------------------------- | ---------------- |
| UI-01 | User can ask a question and receive answer with sources     | E2E test         |
| UI-02 | User can click a source and file opens at exact location    | Manual + E2E     |
| UI-03 | Every answer shows: Sources, Date confidence, Outdated warn | Visual + Unit    |
| UI-04 | "Not found" displays when no sources match query            | E2E test         |
| UI-05 | Indexing progress visible during active job                 | E2E test         |
| UI-06 | Library shows all indexed documents with filters            | E2E test         |
| UI-07 | UI works with no external network requests                  | Network monitor  |
| UI-08 | All pages load in <2 seconds on first visit                 | Performance test |
| UI-09 | Keyboard shortcut `/` focuses query input                   | Unit test        |
| UI-10 | Dark mode toggle works and persists                         | Manual test      |

### Not Just a Skin

The UI is considered successful only if:

1. **Source verification is trivial**: Opening a source at the exact cited location takes one click
2. **Trust is visible**: Date and confidence are impossible to miss
3. **Failures are explicit**: Users never see empty or misleading results
4. **The CLI is optional**: Users who prefer the UI never need the terminal

---

## Test Plan

### Unit Tests (`tests/test_ui_*.py`)

| Test                 | Description                            |
| -------------------- | -------------------------------------- |
| `test_routes`        | All routes return 200 and correct HTML |
| `test_static_assets` | CSS/JS files served correctly          |
| `test_keyboard_nav`  | Keyboard shortcuts trigger actions     |

### Integration Tests

| Test               | Description                                       |
| ------------------ | ------------------------------------------------- |
| `test_ask_flow`    | Query → API call → Answer render → Source display |
| `test_index_flow`  | Start job → Poll progress → Completion toast      |
| `test_open_source` | Click source → `/open` call → Verify instruction  |

### E2E Tests (Playwright or similar)

| Test                  | Description                                       |
| --------------------- | ------------------------------------------------- |
| `test_full_ask`       | Navigate, query, verify answer + footer + sources |
| `test_library_browse` | Filter documents, click, verify details           |
| `test_no_network`     | Monitor network, assert zero external requests    |

### Visual Regression

- Screenshot comparison for key states
- Answer footer always present
- Source cards consistent formatting

---

## Sources

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase 3 requirements
- [API_CONTRACT.md](API_CONTRACT.md) — Endpoint specifications
- [architecture.md](architecture.md) — System design

**Date Confidence:** HIGH (document created 2025-12-23)

---

_This UI plan is a living document. Update as implementation progresses._
