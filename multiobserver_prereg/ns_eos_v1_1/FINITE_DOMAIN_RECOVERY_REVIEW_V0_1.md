# CCSU-MO-NS-EOS-001 — Finite-domain recovery review v0.1

**Status:** recovery candidates found; proposal-box imbalance demonstrated  
**Study class:** deterministic nonconfirmatory diagnostic  
**Pilot entry:** forbidden  
**Confirmatory authorization:** false

## Frozen scope

The search remained inside the four existing proposal boxes and the EOS
domain ending at \(6\,n_{\rm sat}\). It did not clip invalid proposals,
extrapolate pressure, alter the stellar gates, or interpret any box as a
physical prior.

A fixed scrambled Sobol sequence generated 32 proposals per chart. Each
proposal was paired with both registered χEFT members, giving 256 cases.
The same parameter point was used for both members. A 24-point finite-domain
screen rejected cases without a mass turnover or without support through
\(2.2\,M_\odot\); survivors were re-evaluated with the registered 48-point
solver and the full mass-anchor grid.

## Result

There were no numerical rejections. Sixty-five of 256 chart/χEFT cases passed
exact revalidation, representing 33 distinct chart-parameter proposals.

| Chart | Cases | Accepted | Fraction | Principal rejection |
|---|---:|---:|---:|---|
| GW | 64 | 2 | 0.03125 | 38 local-physics rejections |
| XRAY | 64 | 0 | 0 | 45 no-turnover cases |
| RADIO | 64 | 3 | 0.046875 | 44 local-physics rejections |
| NUCLEAR | 64 | 60 | 0.9375 | 4 stellar-gate rejections |

The accepted maximum masses range from \(2.2199\) to
\(3.8400\,M_\odot\). These are finite-domain forward-model results, not
observationally accepted EOSs: observational likelihoods were intentionally
outside this diagnostic.

Thirty NUCLEAR proposals, one GW proposal, and one RADIO proposal passed for
both χEFT members. A second RADIO proposal passed only for N3LO-450.
No XRAY proposal passed.

## Inference

The search answers two different questions:

1. **Can the finite-domain gates be satisfied without extrapolation?** Yes.
   GW, RADIO, and NUCLEAR contain at least one such proposal.
2. **Do the current boxes provide balanced proposal support across charts?**
   No. Acceptance ranges from 0 to 0.9375, so a finite maximum-to-minimum
   ratio is not defined.

The second answer blocks the pilot. Sampling the current boxes directly would
make chart identity a dominant acceptance mechanism and would structurally
favour NUCLEAR. This is a property of the proposal geometry under the common
filters, not evidence that the NUCLEAR observer is scientifically superior.

## Decisions that remain open

1. independently review whether each chart's parameterization and numerical
   bounds cover comparable physically admissible relation space;
2. diagnose the XRAY zero-acceptance region, especially the absence of
   turnover before \(6\,n_{\rm sat}\);
3. decide whether recovery uses reviewed chart-specific proposal measures or
   a new common relation-space proposal mechanism;
4. add observational filters before treating high accepted masses as viable;
5. rerun this diagnostic under a new registered contract after those choices.

The density endpoint, inference rule, and public Atlas semantics remain
unchanged. No candidate enters P1–P4 calibration from this run.
