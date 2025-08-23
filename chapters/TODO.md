# TODO.md — CCSU · E8 · Triality Project
_Generated: today_

This checklist keeps compile hygiene **and** the science pipeline in sync. Keep it beside `labels.md` (same folder).

## A) Build & compile hygiene (every commit)
- [ ] **Preamble order** in `preamble.tex`: load `siunitx` **before** `physics` and include:
      ```tex
      \usepackage{siunitx}
      \usepackage{physics}
      \AtBeginDocument{\RenewCommandCopy\qty\SI}
      ```
- [ ] **Tables toolkit** (in `preamble.tex`, once):
      ```tex
      \usepackage{tabularx,booktabs,array,ragged2e}
      \newcolumntype{L}{>{\RaggedRight\arraybackslash}X}
      \newcolumntype{M}[1]{>{\RaggedRight\arraybackslash}m{#1}}
      ```
- [ ] **No duplicate inputs** for generated files. Only one: `\input{build/gauge_map_check.tex}` (after `gauge_sector.tex`).
- [ ] **Labels source of truth** is `labels.md`. If Overleaf shows *multiply-defined labels*, search & fix before merging.
- [ ] **Over/Underfull boxes**: acceptable only if **<= 15pt** and visually harmless. Current known benign cases:
  - Overfull `\hbox` ~12.7pt at `fig_collapse_compiler.tex` L16–L17 → keep under watch.
  - Underfull `\hbox` at `tab_semantic_invariants.tex` L30 → acceptable layout-wise.
  If they grow, mitigate with `\raggedright` in the float, shorter captions, or `M{<width>}` columns.

## B) Label enforcement (do once; re-run when adding chapters)
- [ ] Use chapter label **`chap:gravity-memory`** (retire `chap:gravity` everywhere).
- [ ] After any label edits: recompile until **no** warnings for multiply-defined **and** undefined references.
- [ ] Use the prefixes: `chap:`, `sec:`, `fig:`, `tab:`, `eq:`, `prop:` only.

### Quick search/replace (Overleaf regex)
- Find duplicates of old gravity label:
  - Find: `\\label\{chap:gravity\}` → Replace: `\\label{chap:gravity-memory}`
  - Find: `\\ref\{chap:gravity\}`   → Replace: `\\ref{chap:gravity-memory}`
- Find any ad-hoc figure refs → Replace with `Fig.~\\ref{...}`:
  - Find: `Figure~\\ref\{([^}]+)\}` → Replace: `Fig.~\\ref{\1}`

## C) Tables (uniform pattern)
- [ ] Convert any `>$l<$` / special math-column hacks to `tabularx` with `L` or `M{..}`.
- [ ] For dense tables, add once near the table:
      ```tex
      \setlength{\tabcolsep}{6pt}
      \renewcommand\arraystretch{1.15}
      ```
- [ ] `tab_semantic_invariants.tex`: ensure final row wraps using `L` columns; avoid manual linebreaks in headers.
- [ ] Generated tables live under `build/` and are **not edited by hand**.

## D) Figures
- [ ] Use `\includegraphics[width=\linewidth]{...}` unless a natural aspect ratio requires smaller width.
- [ ] `fig_collapse_compiler.tex`: if Overfull > 13pt, wrap caption to two lines or reduce figure width to `0.95\linewidth`.

## E) Replication packs → paper wiring
- [ ] **Gauge** (replication_pack_gauge_v1.zip)
  - Run anomaly & Y-map scripts → regenerate `build/gauge_map_check.tex`.
  - Include **once** after `gauge_sector.tex`.
- [ ] **CKM/PMNS** (`ckm_pmns_outputs.zip`)
  - Use provided `build/ckm_pmns_final_latex_table.tex` or regenerate from CSV/JSON.
  - Keep acceptance thresholds in text synced with code output (Jarlskog, angles deltas).
- [ ] **Ringdown** (`ringdown_replication_pack_v1.zip`)
  - Run `ringdown_acceptance.py` on batch (or provided mock) → `build/ringdown_batch_table.tex`.
  - Reference it in the Predictions chapter.
- [ ] **O1/O2/O3 data.zip**
  - (Staged for future ingestion.) Ensure any plots list detector run + event IDs in captions.

## F) Canonical equations & propositions (lock-in)
- [ ] Keep the PDE triplet and energy exactly as labeled in the text:
  - `eq:neutral-pde` (3.1), `eq:energy` (3.2), `eq:lifted-transport` (3.3), plus `eq:ringdown-perturb` (3.6).
- [ ] Propositions A1–A4 are numbered and referenced as `prop:A*...` and their numeric thresholds match code & tables.

## G) E8 → SM mapping (with Mark)
- [ ] Maintain SU(5)-bypass Y mapping until E8 mapping note is finalized.
- [ ] Request from Mark (one-pagers):
  1) **Hypercharge mapping note**: explicit weight-to-Y map and anomaly neutrality sketch.
  2) **Triality → δℓ rationale**: how triality fixes generation indexing without extra free parameters.
- [ ] When received, add as Appendix and update main text references.

## H) Predictions & numeric targets (lab-facing)
- [ ] Ringdown ratio target: **(221/220) frequency ratio drift** predicted by Λ–memory; specify ± tolerance.
- [ ] Low-ℓ CMB semantic residuals (outline location in sky-map; cite dataset used).
- [ ] Mass ladder harmonics: list `m_a = m0 r^{n_a}` fits with residuals per shell (table in `build/`).

## I) Release checklist (pre-PDF freeze)
- [ ] No multiply-defined labels.
- [ ] No undefined references.
- [ ] Preamble loads are de-duplicated; `\qty` hooked to `siunitx`.
- [ ] All generated files are under `build/` and included once.
- [ ] Figure/table captions explain data provenance.
- [ ] Git/Overleaf tag added: `vX.Y (CCSU_E8_ToE)` with date.

## J) Folder norms
