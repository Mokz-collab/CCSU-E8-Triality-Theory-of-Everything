# Labels & References Registry (curated)
_Generated: today_

This file is a **single source of truth** for labels used across the project. Keep it in the Overleaf root (or `docs/`).  
Use the prefixes below and **do not reuse** labels.

## Conventions
- Prefixes: `chap:`, `sec:`, `fig:`, `tab:`, `eq:`, `prop:`.
- Place `\label{...}` immediately after `\chapter{..}`, `\section{..}`, `\caption{..}`, or within the math environment for equations.
- When you rename a label here, rename it in the source and recompile. Avoid duplicates (Overleaf warning: *Label ... multiply defined*).

---

## Chapter labels
- [x] `chap:prologue` — *Prologue: Why Recursion Before Symmetry*
- [x] `chap:primer` — *Semantic Universe Primer*
- [x] `chap:collapse-pdes` — *Collapse PDEs*
- [x] `chap:E8-triality` — *E8 Geometry & Triality*
- [x] `chap:orbits-to-matter` — *From Orbits to Matter*
- [x] `chap:mass-ladders` — *Mass Ladders & Alignment*
- [x] `chap:flavor` — *Flavor & Phases*
- [x] `chap:gravity-memory` — *Gravity as Collapse Memory*  ← **use this; retire any `chap:gravity` duplicates**
- [x] `chap:bh-cores` — *Black–Hole Cores as Echo Knots*
- [x] `chap:overlay` — *Overlay XIII/XIV*
- [x] `chap:contracts` — *Assumptions & Safety Contracts (A1–A4)*
- [x] `chap:adversarial` — *Adversarial ψ–C17 Suite*
- [x] `chap:predictions` — *Predictions & Experiments*
- [x] `chap:novelty-ledger` — *Novelty Ledger vs Known Physics*

## Section labels (key ones referenced in text)
- [x] `sec:semantic-lattice` — §2.4 *E8 as a Semantic Lattice*
- [x] `sec:layer-invariants` — §2.5 *Layer Invariants*
- [x] `sec:dynamics` — §3.1 *Dynamics*
- [x] `sec:e8-embedding` — §4.1 *Embedding*
- [x] `sec:ringdown-memory` — §8.1 *Memory as collapse*

## Figure labels
- [x] `fig:semantic-ladder` — Fig. 2.1 *Semantic ladder: collapse writes energy → information → meaning*
- [x] `fig:collapse-compiler` — Fig. 2.2 *Collapse as compiler*
- [x] `fig:e8-semantic-lattice` — Fig. 2.3 *Conceptual E8 semantic lattice*

## Table labels
- [x] `tab:semantic-invariants` — Tab. 2.1 *Layer invariants / how measured*
- [x] `tab:hypercharge-one-family` — Tab. 4.1 *SU(5) bypass — one family Y (calc vs exp)*
- [x] `tab:geom-192` — Tab. 5.1 *Geometric 192-state superset*
- [x] `tab:mass-ladders` — Tab. 6.1 *Mass ladders by shells*
- [x] `tab:alignment-residuals` — Tab. 6.2 *{W,Z,h,t} alignment residuals*
- [x] `tab:mixing-summary` — Tab. 7.1 *CKM/PMNS angles and J*

## Equation labels (canonical)
- [x] `eq:logmass-regression` — (2.1) log–mass regression on E8 weights
- [x] `eq:neutral-pde` — (3.1) convective collapse (neutral)
- [x] `eq:energy` — (3.2) Lyapunov energy
- [x] `eq:lifted-transport` — (3.3) observer–lifted transport
- [x] `eq:neutral-ginzburg` — (3.4) neutral GL form
- [x] `eq:lifted-memory` — (3.5) lifted GL + memory
- [x] `eq:ringdown-perturb` — (3.6) δω/ω ≈ α_Λ Ξ (220) and 221/220 ratio
- [x] `eq:mass-ladder` — (6.1) harmonic mass shells m_a = m0 r^{n_a}
- [x] `eq:alignment` — (6.2) alignment projector
- [x] `eq:Seff` — (8.1) effective action with Λ–memory

## Proposition labels (A1–A4)
- [x] `prop:A1-idempotence` — A1 Idempotence
- [x] `prop:A2-spectrum` — A2 Spectrum stability
- [x] `prop:A3-generation-lock` — A3 Generation–lock
- [x] `prop:A4-safety` — A4 Safety (shock fallback)

---

## How to use (copy–paste)
**Chapters**  
\chapter{Gravity as Collapse Memory}\label{chap:gravity-memory}

**Sections**  
\section{E8 as a Semantic Lattice}\label{sec:semantic-lattice}

**Figures / tables**  
\begin{figure}[t]
  \centering
  ... 
  \caption{Conceptual E8 semantic lattice}\label{fig:e8-semantic-lattice}
\end{figure}

\begin{table}[t]
  \centering
  ...
  \caption{Summary of layer invariants}\label{tab:semantic-invariants}
\end{table}

**Equations**  
\begin{equation}\label{eq:neutral-pde}
  \partial_t \psi + \nabla\cdot\big(v(\psi)\,\psi\big) = -\alpha |\psi|^2\psi + \beta\,\Delta\psi.
\end{equation}

---

## Sanity checklist (tick on each compile)
- [ ] No *multiply defined* labels (search for: `LaTeX Warning: There were multiply-defined labels.`).
- [ ] No *undefined references* (search for: `LaTeX Warning: There were undefined references.`).
- [ ] If you still have `Label \`chap:gravity' multiply defined`, **rename all uses** to `chap:gravity-memory` (project-wide).

> Tip: In Overleaf, use *Search (.*)* to find `\label{chap:gravity}` and replace with `\label{chap:gravity-memory}`; also update any `\ref{chap:gravity}`.
