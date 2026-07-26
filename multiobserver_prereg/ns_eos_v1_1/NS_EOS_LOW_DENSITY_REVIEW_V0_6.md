# CCSU-MO-NS-EOS-001 — Low-Density Review v0.6

**Status:** outer-crust, unified-EOS oracles, and χEFT inputs pinned;
revised connector passed local calibration/holdout, final-pairing, and internal
stellar-impact validation  
**Scientific use:** development only; no confirmatory authorization

## Material corrections through v0.4

The draft phrase “BPS crust through \(0.5\,n_{\rm sat}\)” collapsed two
physically distinct regimes into one label. In its strict use, the BPS-family
treatment describes the outer crust down to neutron drip. The inner crust
contains unbound neutrons and requires a separate microscopic model or a
declared connector.

The development contract therefore uses three explicit segments:

1. pinned modern BPS-formalism **outer-crust** ensemble: surface to the
   model-specific neutron-drip endpoint;
2. one shared **inner-crust connector**: neutron drip to
   \(0.5\,n_{\rm sat}\);
3. two pinned MUSES χEFT reference members: \(0.5\) to
   \(1.1\,n_{\rm sat}\).

This is not merely terminological. Treating the connector as if it were BPS
would hide a modelling choice from provenance and could make apparent
multi-observer agreement depend on an unregistered common assumption.

Primary anchors:

- Baym, Pethick & Sutherland (1971):
  https://ui.adsabs.harvard.edu/abs/1971ApJ...170..299B/abstract
- CompOSE reference manual and standardized units:
  https://arxiv.org/abs/2203.03209
- Hebeler et al. chiral-EFT constraints and representative EOS tables:
  https://arxiv.org/abs/1303.4662
- Modern explicit outer/inner-crust separation:
  https://arxiv.org/abs/2604.26952
- MUSES χEFT module v1.0.1:
  https://gitlab.com/nsf-muses/chiral-eft-eos/chiral_eft_eos/-/tree/6cf7fea41d2a2bac5f93e567d71279631168088b
- MUSES neutron-star workflow:
  https://arxiv.org/abs/2502.07902

## Canonical representation

Every accepted low-density table must contain exactly:

| Field | Unit |
|---|---|
| baryon density \(n\) | \(\mathrm{fm}^{-3}\) |
| pressure \(P\) | \(\mathrm{MeV\,fm}^{-3}\) |
| energy density \(\varepsilon\) | \(\mathrm{MeV\,fm}^{-3}\) |
| baryon chemical potential \(\mu\) | \(\mathrm{MeV}\) |
| squared sound speed \(c_s^2\) | dimensionless, \(c=1\) |

The loader verifies the byte-level SHA-256 before parsing. Direct upstream
tables must also match their pinned Git blob. Deterministically generated
tables must instead close the chain from pinned source commit through
generator, generation record, configuration, raw output, and final table
hashes. The loader refuses missing licence metadata, a false redistribution
permission, changed columns, non-finite values, non-monotone density or energy,
acausal sound speed, and a violation of

\[
\mu=\frac{\varepsilon+P}{n}.
\]

Four scientific outer-crust tables are embedded as byte-identical copies of
upstream commit `d569b24d072d6746943ef6d107dabd6458d9730b`: DD-ME2, DD-PC1,
DD-PCX, and ELMA. Their upstream Git blob identities, SHA-256 digests, CC BY
4.0 licence, citation, immutable URLs, and retrieval timestamp are checked
before parsing. The separate CSV fixtures remain explicitly marked
`SYNTHETIC_TEST_ONLY`.

The four tables are not averaged. They define a balanced nuisance factor shared
by every observer and every inference arm within a paired trajectory. This
preserves the discrete nuclear-model provenance and prevents the outer crust
from becoming an observer-specific prior.

## Pinned χEFT reference members

The nuclear segment contains two coherent members generated from the MUSES
Chiral EFT EoS v1.0.1 tag, resolved to commit
`6cf7fea41d2a2bac5f93e567d71279631168088b`:

- N3LO-414;
- N3LO-450.

The calculation is at zero temperature. The MUSES many-body calculation is
performed for symmetric and pure-neutron matter; the documented quadratic
interaction-energy approximation supplies intermediate asymmetry. A
charge-neutral electron/muon gas is added and the proton fraction is solved
from beta equilibrium. The published rows cover
\(n_B=0.080\)–\(0.176\;\mathrm{fm}^{-3}\), exactly
\(0.5\)–\(1.1\,n_{\rm sat}\) for the frozen
\(n_{\rm sat}=0.16\;\mathrm{fm}^{-3}\).

MUSES v1.0.1 contains a reproducible key mismatch for N3LO-414: the fitted
parameter file writes `cD/cE`, whereas the parser reads `c_D/c_E`. The
generator normalizes only those two key names. It preserves the source
numerical values \(-0.400\) and \(-0.072\), records the normalization in the
generation manifest, and changes no scientific coefficient.

These two members define a **coherent interaction reference envelope**. They
are not a formal order-by-order χEFT truncation band and have no registered
probabilistic coverage. A trajectory selects one complete member and uses it
for every observer and inference arm. Pointwise selection, coefficient
averaging, table averaging, and observer-conditioned selection are forbidden.

The generator, source commit, tag object, source-file hashes, configs, raw
outputs, canonical tables, environment, and timestamps are all registered.
The upstream GPL-3.0-or-later notice is carried with the generated products.

## Rejected endpoint-only connector

Let \(x=(n-n_0)/(n_1-n_0)\). The connector represents the chemical potential as

\[
\mu(x)=\mu_0+(\mu_1-\mu_0)
\frac{\exp(kx)-1}{\exp(k)-1}.
\]

The shape \(k\) is not sampled. It is solved from the endpoint pressure
difference so that

\[
P_1-P_0=\int_{\mu_0}^{\mu_1}n\,d\mu.
\]

Energy and pressure are then derived, not independently interpolated:

\[
dP=n\,d\mu,\qquad
\varepsilon=n\mu-P,\qquad
c_s^2=\frac{n}{\mu}\frac{d\mu}{dn}.
\]

Consequently, all endpoint values and the cold-matter thermodynamic identities
are satisfied exactly up to floating-point tolerance. That exactness was
necessary but not sufficient. Against licensed unified-EOS tables, the
one-parameter shape produced large interior discrepancies while still closing
both endpoints.

For IOPB, its density-weighted RMS log-pressure error was \(0.201\) and the
maximum was \(0.693\). For the held-out G3 table, the corresponding values were
\(0.165\) and \(0.588\). Both exceed the registered development thresholds
\(0.08\) and \(0.15\). The normalized chemical-potential-span criteria also
failed in both tables. The endpoint-only normalized exponential is therefore
retired from the active rule and retained in code only as a negative-control
baseline.

## Reference-tilted connector

The replacement keeps the endpoint identities but supplies a fixed positive
template for the normalized derivative \(g(x)=dh/dx\):

\[
g_0(x)=\sum_{j=1}^{3}
\frac{w_j}{\int_0^1 e^{q_jt}\,dt}\,e^{q_jx},
\]

with

\[
q=(-40,0,40),\qquad
w=(0.1019714037,\;0.8427348093,\;0.0552937870).
\]

The weights are non-negative and sum to one. They were obtained by
density-weighted non-negative least squares using only the IOPB unified EOS.
For a new endpoint pair, the active derivative is

\[
g_k(x)=\frac{g_0(x)e^{kx}}
{\int_0^1g_0(t)e^{kt}\,dt},
\]

where the common tilt \(k\) is solved deterministically from the endpoint
pressure difference. There is no sampled inner-crust parameter and no
observer-specific value. Integrating \(g_k\) gives \(h\), after which
\(\mu\), \(P\), \(\varepsilon\), and \(c_s^2\) follow from the same exact
thermodynamic identities as before.

This template is a shared modelling assumption, not a probabilistic prior.
It has no confidence level or coverage probability.

## Internal and external validation

For a synthetic relativistic \(\Gamma=2\) polytrope, the endpoint solution gives
\(k=0\), reducing the bridge to the exact linear chemical-potential relation.
The connector reproduces all registered intermediate values of \(P\),
\(\varepsilon\), \(\mu\), and \(c_s^2\).

Negative tests confirm rejection of:

1. a modified table hash;
2. non-redistributable table bytes;
3. a violated chemical-potential identity;
4. endpoint spans incompatible with \(dP=n\,d\mu\);
5. noncanonical column order or units;
6. a broken deterministic generation chain;
7. a χEFT envelope that claims unregistered probabilistic coverage.

Three unified EOSs from Das et al. (2022) are embedded as exact bytes from
Git commit `80eadb3820c337765659bd204719cedba2221649`, with upstream Git blob
identities and the repository's GPL-3.0-only licence:

| Role | EOS | Rows in registered slice | Upper anchor (\(\mathrm{fm}^{-3}\)) |
|---|---:|---:|---:|
| calibration only | IOPB | 241 | 0.08113221 |
| primary holdout | G3 | 171 | 0.07398835 |
| advisory coarse-grid holdout | FSUGarnet | 105 | 0.1079765 |

G3 and FSUGarnet were not used to determine the template weights. The metrics
use trapezoidal density weights for \(P\) and \(\mu\), and density-interval
weights for the secant \(dP/d\varepsilon\) comparison.

The revised connector passed every registered primary metric for IOPB and G3.
On the primary holdout G3:

| Metric | v0.4 baseline | v0.5 candidate | Limit |
|---|---:|---:|---:|
| RMS \(|\log(P_{\rm bridge}/P_{\rm EOS})|\) | 0.1649 | 0.03190 | 0.08 |
| maximum log-pressure error | 0.5884 | 0.06119 | 0.15 |
| RMS \(|\Delta\mu|/(\mu_1-\mu_0)\) | 0.04794 | 0.006176 | 0.02 |
| maximum normalized \(\mu\) error | 0.09967 | 0.01392 | 0.04 |
| RMS absolute \(c_s^2\) interval error | 0.000979 | 0.000937 | 0.002 |

FSUGarnet also passed the looser predeclared advisory thresholds. It is not a
primary gate because its nearest upper row to \(0.08\,\mathrm{fm}^{-3}\) lies
at \(0.1079765\,\mathrm{fm}^{-3}\) after a large table gap.

The fit and validation replay byte-for-byte from their frozen scripts,
manifests, timestamps, and environment records.

## Final endpoint pairings

Every allowed combination of four outer-crust members and two MUSES members
was joined and sampled at 2,049 density points. The Koliogi tables round the
tabulated neutron-drip chemical potential. Their endpoint residuals in
\(\mu=(\varepsilon+P)/n\) range from \(6.25\times10^{-8}\) to
\(2.45\times10^{-7}\).

The pairing contract therefore preserves the source \(n,P,\varepsilon,c_s^2\)
and derives only \(\mu=(\varepsilon+P)/n\), provided the original residual is
at most \(10^{-6}\). This projection is recorded for every pair; it is never
silent, and a larger correction is rejected.

All eight pairings pass endpoint reconstruction, the exact identity,
strictly increasing \(P,\varepsilon,\mu\), and \(0<c_s^2<1\). Their solved
template tilts span \(-1.08187\) to \(-1.05007\), and sampled \(c_s^2\) spans
\(3.40\times10^{-4}\) to \(2.39\times10^{-2}\).

## Conditional stellar-impact test

To isolate low-density sensitivity, every pair and both connector rules were
attached above \(1.1\,n_{\rm sat}\) to the same synthetic constant-sound-speed
extension, \(c_s^2=0.6\). This is a diagnostic common core, not an
astrophysical high-density prior. The internal TOV/Love implementation solved
fixed masses \(1.0,1.4,2.0\,M_\odot\).

Across all pairs and target masses:

| Quantity | Maximum observed | Development limit |
|---|---:|---:|
| candidate–baseline radius difference | 0.001405 km | 0.05 km |
| candidate–baseline relative \(\Lambda\) difference | 0.01929 | 0.02 |
| radius spread from outer-crust choice | 0.004395 km | 0.02 km |
| fractional \(\Lambda\) spread from outer-crust choice | 0.0005437 | 0.01 |

For the registered \(1.4\,M_\odot\) convergence case, halving the maximum
radial step changed the radius by \(2.98\times10^{-6}\) fractionally and
\(\Lambda\) by \(3.45\times10^{-3}\), below the respective \(10^{-3}\) and
\(5\times10^{-3}\) limits.

## Remaining evidential gap

The local thermodynamic-shape component of external validation is now complete
for this development checkpoint. It does not establish adequacy for arbitrary
crust microphysics, nor does it validate the final Koliogi–MUSES endpoint
pairings.

The final pairings and their conditional stellar sensitivity are now tested
internally. Before freeze, the physical TOV/Love results must still agree with
an independent implementation. The two-member MUSES envelope must also not be
promoted to a calibrated χEFT uncertainty distribution without a separate,
predeclared order-by-order error model.

## Decision

The outer-crust ensemble, χEFT reference members, semantic corrections, and
reference-tilted development connector are accepted for continued
implementation. The low-density layer still does **not** authorize a public
confirmatory freeze because independent TOV/Love agreement, independent range
review, P1–P4 calibration, and the power-derived budget remain open.
