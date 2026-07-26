# CCSU-MO-NS-EOS-001 — Low-Density Review v0.4

**Status:** outer-crust and χEFT reference inputs pinned; thermodynamic
connector implemented; external validation pending  
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

## Shared inner-crust connector

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
are satisfied exactly up to floating-point tolerance. The connector is common
to all observers and has no observer-specific free parameter.

## Internal validation

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

## Remaining evidential gap

Internal exactness does not establish that this connector is an adequate model
of the physical inner crust. Before freeze, it must be compared against at
least one pinned unified EOS across neutron drip to \(0.5\,n_{\rm sat}\), with a
predeclared discrepancy metric for \(P\), \(\mu\), \(c_s^2\), radius, and tidal
deformability.

The outer-crust and χEFT input-byte/licence blockers are resolved. What remains
is external adequacy testing: the inner-crust connector must be compared with
a pinned unified EOS, and the two-member MUSES envelope must not be promoted to
a calibrated χEFT uncertainty distribution without a separate, predeclared
order-by-order error model.

## Decision

The outer-crust ensemble, χEFT reference members, semantic corrections, and
development connector are accepted for continued implementation. The
low-density layer still does **not** authorize a public confirmatory freeze
because external inner-crust validation, independent code review, and
end-to-end stellar validation remain open.
