# AccessCast site redesign brief

Reference and inspiration: https://dontboardme.com/ (studied page by page on 16 Oct 2026). We take its **spirit and patterns**, never its code, images, fonts, copy or brand. Everything here is our own build, and it must stay accessible: keyboard only, screen readers, `prefers-reduced-motion`, axe-core 0 violations, plain words.

## What we take from the reference (patterns, not assets)
- Giant condensed all-caps display type set against tiny uppercase micro-captions.
- Each section has its own background colour, and the page changes colour as you scroll.
- Big circles everywhere: discs with text running around their edge (slowly rotating), half-circle section edges, circular image masks.
- Pill buttons with a small dot or arrow ("BOOK NOW •" → ours: "WATCH IT •").
- An orbit for "How it works?": numbered steps placed around a big circle.
- Big list rows set in display type with values on the right (their price rows → ours: results and law dates).
- A playful interactive moment at the top (their ball-bounce gate). **Ours must never block the site**: an optional "Close your eyes" listening toggle in the hero.
- Footer with small-caps link columns and a chunky stacked wordmark.

## Palette (ours; every text/background pair checked for WCAG AA)
| Token | Hex | Use |
|---|---|---|
| `--paper` | #F6F1E7 | default background (warm cream) |
| `--ink` | #141B34 | body text, deep navy-black |
| `--signal` | #E4402A | display type and primary buttons on paper (large text only; use `--signal-dark` #B92D1A for small text) |
| `--sun` | #FFD23F | the "sound dot" accent (never text on paper) |
| `--blind-bg` / `--blind-ink` | #1B1E4B / #FFD23F | "I can't see the screen" world |
| `--deaf-bg` / `--deaf-ink` | #C9EBDC / #0E4A35 | "I can't hear" world |
| `--easy-bg` / `--easy-ink` | #FFD9C2 / #8A2F0B | "Simpler words, please" world |
| `--hi-bg` / `--hi-ink` | #F9C74F / #4A1942 | हिन्दी world |
| `--it-bg` / `--it-ink` | #BFDDF5 / #12355B | Italiano world |
Dark mode: `--paper` #10142B, `--ink` #F6F1E7, signal #FF6B52; audience worlds keep their hues, slightly deeper.

## Type (self-hosted, OFL; added to MODEL_LICENSES.md "Fonts")
- Display: **Anton** (condensed, all caps), sizes clamp(56px, 11vw, 200px) for heroes.
- Body and UI: **Inter** (variable), 18px base, line-height 1.5.
- Devanagari: **Noto Sans Devanagari** for every `lang="hi"` element.
- Micro-captions: Inter 12–13px, uppercase, letter-spacing 0.08em; never below 12px, and still AA contrast.

## Motion (all off under `prefers-reduced-motion: reduce`)
- Reveal on scroll: fade + 24px rise, staggered, IntersectionObserver; no scroll hijacking, no smooth-scroll libraries.
- Section colour transitions: the body background eases between section colours as each section crosses the middle of the viewport.
- Rotating circle text (40 s per turn), paused on hover and focus.
- Discs drift with gentle parallax on scroll.
- Pill buttons: arrow nudges 4px on hover/focus.
- A marquee of the five picker labels (pausable with a visible button, WCAG 2.2.2).
- Live sound visual in the hero: speech blocks and description blocks on a timeline, drawn from real data, animated as audio plays.

## Pages
1. **`index.html` (new landing)**, sections in order:
   1. Hero: "ONE VIDEO. FIVE WAYS TO WATCH." rotating disc with "GEMMA 4 ON AMD INSTINCT MI300X • ", pill "WATCH IT •" → player; micro-caption.
   2. "Close your eyes": two pill toggles, *Original sound* and *With AccessCast description*, playing the fixture clip's audio, with a timeline of speech and description blocks (from `p/<sha12>/decisions.json` and the analysis). Keyboard operable; announces what is playing.
   3. "Who's watching?": five big audience discs, each in its world colour, label on the circle edge, opening `watch.html?audience=<id>`.
   4. "How it works?": orbit with six numbered steps (Listen, Look, Plan, Write, Check, Approve); one step at a time is highlighted as you scroll, with a plain sentence for each; also a keyboard-operable step list.
   5. "Gemma proposes. Code decides.": rule chips demo from `data/rule_examples.json` (real rule output, precomputed by `scripts/build_rule_examples.py`): pick an example line and see which checks fire, with observed vs limit.
   6. Results rows (display type, values right-aligned) read from `data/claims.json`; a value not measured yet shows "Measuring" — never a number we don't have.
   7. "The law already asks": big rows with dates from `data/claims.json` (cited facts) and a half-circle section edge.
   8. Proof teaser disc → `proof.html`.
   9. Footer: stacked wordmark, link columns, disclosure line.
2. **`watch.html`** (the player, moved from index.html; `index.html?audience=…` or `?p=…` redirects there so old links keep working): same functionality and tests as today, restyled. The picker is five discs that switch the page into that audience's colour world.
3. **`five-ways.html`** and **`proof.html`**: restyled in the same system.

## Hard rules
- No number on any page unless it comes from `data/claims.json` (built from `evidence/public-claims.json`) or is the plain count of something on screen.
- The fixture is labelled as a demo fixture with canned outputs wherever it appears.
- No external network requests at runtime; fonts self-hosted.
- Every existing e2e test keeps passing (paths updated where the player moved), plus axe-core runs on the new landing page.
