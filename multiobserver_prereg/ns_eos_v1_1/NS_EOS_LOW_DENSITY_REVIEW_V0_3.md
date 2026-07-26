# CCSU-MO-NS-EOS-001 — Low-Density Review v0.3

**Status:** format, units, hash gate, and thermodynamic connector implemented;
scientific source bytes pending  
**Scientific use:** development only; no confirmatory authorization

## Material correction to v0.2

The draft phrase “BPS crust through \(0.5\,n_{\rm sat}\)” collapsed two
physically distinct regimes into one label. In its strict use, the BPS-family
treatment describes the outer crust down to neutron drip. The inner crust
contains unbound neutrons and requires a separate microscopic model or a
declared connector.

The development contract therefore uses three explicit segments:

1. pinned BPS-family **outer-crust** table: surface to neutron drip;
2. one shared **inner-crust connector**: neutron drip to
   \(0.5\,n_{\rm sat}\);
3. chiral-EFT-spanning band: \(0.5\) to \(1.1\,n_{\rm sat}\).

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

## Canonical representation

Every accepted low-density table must contain exactly:

| Field | Unit |
|---|---|
| baryon density \(n\) | \(\mathrm{fm}^{-3}\) |
| pressure \(P\) | \(\mathrm{MeV\,fm}^{-3}\) |
| energy density \(\varepsilon\) | \(\mathrm{MeV\,fm}^{-3}\) |
| baryon chemical potential \(\mu\) | \(\mathrm{MeV}\) |
| squared sound speed \(c_s^2\) | dimensionless, \(c=1\) |

The loader verifies the byte-level SHA-256 before parsing. It refuses missing
licence metadata, a false redistribution permission, changed columns,
non-finite values, non-monotone density or energy, acausal sound speed, and a
violation of

\[
\mu=\frac{\varepsilon+P}{n}.
\]

No scientific table has yet been embedded. The checked-in CSV files are
explicitly marked `SYNTHETIC_TEST_ONLY`.

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
5. noncanonical column order or units.

## Remaining evidential gap

Internal exactness does not establish that this connector is an adequate model
of the physical inner crust. Before freeze, it must be compared against at
least one pinned unified EOS across neutron drip to \(0.5\,n_{\rm sat}\), with a
predeclared discrepancy metric for \(P\), \(\mu\), \(c_s^2\), radius, and tidal
deformability.

The outer-crust and EFT bytes also remain unselected because “downloadable” is
not sufficient provenance. The exact asset, immutable URL, SHA-256, citation,
licence or permission text, and redistribution status must all be registered
before the file enters the repository.

## Decision

The correction and the development connector are accepted. The low-density
layer is structurally implementable but does **not** yet satisfy the public
freeze blocker for scientific source data.
