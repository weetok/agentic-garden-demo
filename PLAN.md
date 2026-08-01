# Agentic Garden Demo — Build Plan

> A two-evening MVP demonstrating a sensor-to-advice pipeline for a real allotment:
> data sources, data flow, dashboards, and an explainable weekly briefing.
> Built as a shareable, self-contained public demo — a clickable URL, not a screen-share.

---

## 1. Demo narrative — "The week the rain missed"

Open on the weekly briefing: a hot, dry week behind, more ahead — and one headline
advice: deep-water the square-foot beds and mulch them; leave the apple guild alone.
Then unwrap it: the regional forecast promised 10 mm of rain; the site rain gauge
caught 2 mm. Wind and heat pushed evapotranspiration well above rainfall — the trend
chart shows the water deficit opening day by day. The planting map knows the
square-foot beds hold shallow-rooted crops while the guild's trees root deep and its
ground layer holds moisture — which is why the advice differentiates rather than
saying "water everything". Close on the data-flow view: rain gauge, wind vane,
hygrometer, thermometer over LoRa, weather API, planting map, observations — one
pipeline, one explainable decision, every week.

---

## 2. Scope

### Must show
- Weekly briefing artefact (rendered markdown)
- Allotment overview with local metrics and headline advice + "why" trace
- Water-balance chart: cumulative ET vs rainfall, site vs regional divergence
- One specific, computed, explained advice (differentiated per bed)
- Data-flow view (animated pipeline, canned)
- LoRa / solar origin present in the flow view and narrative (not demonstrated)

### Won't show
- Live ingestion, LoRa hardware, orchestration internals, real ML, auth
- More than ~3 weeks of mock history

### Mock philosophy
- Data may be mocked; **specificity may not**. The advice must be computed from the
  mock data via the derived layer — never hand-written.
- The data contracts are the stable interfaces of this demo and are kept honest.
  Everything between them may take shortcuts.
- Documentation shows the intended target architecture, with explicit "demo
  shortcut" annotations wherever the demo deviates from it.
- Weather data is authored, not live: the narrative needs a forecast-vs-site
  divergence that real weather won't produce on cue. It is kept in Open-Meteo's
  exact JSON shape so a swap to the live API is a config change.

---

## 3. Architecture

Four mock sources → data contracts (honest) → ingestion + store (shortcuts allowed,
SQLite or flat files fine) → derived layer (honest: ET, water balance, advice rules)
→ two surfaces (dashboard, weekly briefing).

**Honest seams (contracts):**
1. Sensor payload schema — incl. battery/solar voltage field
2. Store / derived-data schema
3. Briefing format

**Stack:** Python pipeline (computes the derived layer, emits JSON + briefing
markdown) + static single-page HTML/JS dashboard (Chart.js for trends, hand-rolled
SVG for the bed map and flow animation). No server. Deployed to GitHub Pages — the
demo is a public URL.

**Target runtime note:** the intended production shape runs the pipeline as a
scheduled job on a Kubernetes cluster with live sensor ingestion over LoRa. The demo
deliberately replaces this with a locally run pipeline committing static output —
annotated as a demo shortcut in the architecture diagrams.

**Repository layout:**

```
contracts/   # the three schemas — the honest seam, visible in the tree
data/        # authored mock inputs (sensor series, weather, planting map, observations)
pipeline/    # Python: derived layer + briefing generator
docs/        # static site, served by GitHub Pages (main branch /docs)
```

**Surfaces, in demo order:**
1. Allotment overview (landing) — bed map from planting YAML, beds coloured by water
   stress, metric cards, advice card with "why" trace beside the map
2. Water balance / trends
3. Data flow (animated)
4. Weekly briefing (rendered)

---

## 4. Pre-work (before evening 1)

| # | Task | ~Time | Notes |
|---|------|-------|-------|
| P1 | Author planting map YAML | 45 min | From drone photo + garden planner overview. Fields: bed id, position, crops, root-depth class, water need, mulch status. **Blocks the overview page.** |
| P2 | Create repository | 20 min | Public, MIT licence. Enable GitHub Pages (main branch, `/docs`), confirm an empty `index.html` serves. |
| P3 | Devcontainer scaffold | 15 min | Python 3.12 + Node. |

---

## 5. Evening 1 — the showable surface

**Definition of Done:** a public Pages URL showing the overview page with the real
bed map, metric cards, advice card, and the rendered briefing — even if every number
is a hand-typed stub.

| Block | ~Time | Task |
|-------|-------|------|
| 1.1 | 30 min | **Contracts first.** Write the three schemas (sensor payload, derived JSON, briefing format). Hand-authored. |
| 1.2 | 45 min | Dashboard shell: tabs, layout grid, metric cards. |
| 1.3 | 60 min | Overview view: bed map SVG generated from planting YAML, stress colouring from a stub JSON conforming to the derived-data contract. |
| 1.4 | 30 min | Briefing page: markdown render of a hand-written briefing following the contract. |

**Evening 1 cut-line:** trends and flow tabs exist as empty stubs. Acceptable.

---

## 6. Evening 2 — make the specificity honest

**Definition of Done:** the advice on screen is computed — mock data in, ET and
water balance out, differentiated advice from the planting map, briefing regenerated
by the pipeline.

| Block | ~Time | Task |
|-------|-------|------|
| 2.1 | 30 min | Mock data authoring: 3-week hourly sensor series + Open-Meteo-shaped weather JSON with the drought story baked in (week 1 normal; weeks 2–3 heat and wind; regional forecast 10 mm, gauge 2 mm). |
| 2.2 | 75 min | Derived layer (Python): **Hargreaves ET — not full Penman–Monteith** (out of scope by decision; do not enter). Water balance, threshold rules against planting-map attributes, emit derived JSON + briefing markdown. LLM API for advice phrasing only, with template fallback. |
| 2.3 | 30 min | Water-balance chart: Chart.js, cumulative ET vs rainfall, divergence marked. |
| 2.4 | 60 min | Flow animation: self-contained SVG/JS panel, canned pulses source → contracts → store → derived → surfaces. |

**Cut order when time runs out:**
1. Flow animation → degrade to a static flow diagram
2. Advice phrasing → drop the API call, template only
3. Chart → drop the divergence annotation

**Never cut block 2.2.** Computed advice is the demo's integrity.

---

## 7. Risks

| Risk | Where | Escape |
|------|-------|--------|
| Styling perfectionism | Evening 1 | "Good enough, commit, next block" |
| ET-formula depth | Evening 2 | Hargreaves is the ceiling for this demo |
| Mock-data realism polishing | Evening 2 | The story needs to be plausible, not perfect |

---

## 8. Accompanying documentation (after the build, not a third evening)

1. README: what this is, what's mocked, link to the live demo
2. Architecture diagrams (context + container) exported with demo-shortcut
   annotations
