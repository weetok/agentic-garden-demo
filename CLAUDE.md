# CLAUDE.md — Agentic Garden Demo

## What this is
A two-evening demo of a sensor-to-advice pipeline for a real allotment: mock data
in, computed water-balance advice out, presented as a static dashboard and a weekly
briefing. See PLAN.md for the full build plan; work proceeds block by block.

## Stack
- Python 3.12 pipeline in `pipeline/` — computes ET, water balance, advice; emits
  JSON and briefing markdown into `docs/data/`
- Static single-page dashboard in `docs/` (vanilla JS + Chart.js + hand-rolled
  SVG), served by GitHub Pages from main branch `/docs`
- No server, no build step, no framework

## Hard rules
1. **Data may be mocked; specificity may not.** Advice shown on the dashboard must
   be computed by the pipeline from the mock inputs — never hand-written into the
   output.
2. **Never modify anything in `contracts/` without asking first.** The three
   schemas (sensor payload, derived JSON, briefing format) are the stable
   interfaces of this demo.
3. **ET method is Hargreaves.** Do not implement or suggest full FAO-56
   Penman–Monteith; it is out of scope by decision.
4. **No new dependencies without asking.** The dependency list stays minimal.
5. **No secrets in the repo.** The LLM API key comes from an environment variable;
   the pipeline must run (with template-based advice phrasing) when the key is
   absent.
6. When a block's Definition of Done is met, stop — commit rather than polish.

## Conventions
- British English in all text output, metric units throughout
- Mock data lives in `data/`, is hand-authored or generated once, and is committed
- Dashboard reads only from `docs/data/*.json` — it never computes domain logic
- Keep the dashboard a single `index.html` with one JS and one CSS file unless
  there is a concrete reason to split

## Current state
<!-- Update this line at the end of each session -->
Status: pre-work — repo scaffolding.
