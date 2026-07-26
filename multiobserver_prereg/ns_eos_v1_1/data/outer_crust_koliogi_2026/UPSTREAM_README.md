# Outer-Crust Equations of State

EOS tables for the outer crust of neutron stars based on modern nuclear mass models.

This repository provides the outer-crust equation-of-state (EOS) tables used in the paper:

**P. S. Koliogiannis and N. Paar**  
**Outer-Crust Equations of State for Neutron Stars**  
arXiv:2604.26952 [nucl-th]  
https://arxiv.org/abs/2604.26952

## Overview

The tables correspond to outer-crust EOSs for neutron stars constructed from four nuclear mass models:

- DD-ME2
- DD-PC1
- DD-PCX
- ELMA

Experimental nuclear masses from AME2020 are used wherever available, while the theoretical models determine the equilibrium composition in the neutron-rich region beyond current experimental coverage.

These tables are intended for use in neutron-star calculations and related astrophysical applications.

## Repository contents

This repository currently includes the following EOS tables:

- `EOS_DDME2.dat` — outer-crust EOS based on the DD-ME2 mass model
- `EOS_DDPC1.dat` — outer-crust EOS based on the DD-PC1 mass model
- `EOS_DDPCX.dat` — outer-crust EOS based on the DD-PCX mass model
- `EOS_ELMA.dat` — outer-crust EOS based on the ELMA mass model

Each file contains the following columns:

1. `density`
2. `A`
3. `Z`
4. `Nucleus`
5. `energy`
6. `pressure`
7. `chemical_potential`
8. `electron_chemical_potential`
9. `B/A`
10. `Gamma`
11. `cs/c`
12. `BE_source`

## Column definitions and units

The columns in each `.dat` file are:

- `density` — baryon number density, $n_b~[{\rm fm^{-3}}]$
- `A` — mass number of the equilibrium nucleus, $A$
- `Z` — proton number of the equilibrium nucleus, $Z$
- `Nucleus` — nuclide label
- `energy` — energy density, $\mathcal{E}$ $[{\rm MeV~fm^{-3}}]$
- `pressure` — pressure, $P~[{\rm MeV~fm^{-3}}]$
- `chemical_potential` — chemical potential, $\mu$ $[{\rm MeV}]$
- `electron_chemical_potential` — electron chemical potential, $\mu_e$ $[{\rm MeV}]$
- `B/A` — binding energy per nucleon, $B/A$ $[{\rm MeV}]$
- `Gamma` — adiabatic index, $\Gamma$ [dimensionless]
- `cs/c` — speed of sound in units of speed of light, $c_{s}/c$ [dimensionless]
- `BE_source` — source of the nuclear binding energy used for the equilibrium nucleus (`exp` for AME2020 or `the` for the corresponding theoretical model)

Units follow standard nuclear-astrophysics conventions.

## Notes

- The files are provided for research use in neutron-star structure calculations and related applications.

## Citation

If you use these EOS tables, please cite as:

```bibtex
@misc{koliogiannis2026outercrustequationsstateneutron,
      title        = {Outer-Crust Equations of State for Neutron Stars},
      author       = {P. S. Koliogiannis and N. Paar},
      year         = {2026},
      eprint       = {2604.26952},
      archivePrefix= {arXiv},
      primaryClass = {nucl-th},
      url          = {https://arxiv.org/abs/2604.26952}
}
```

Once the journal version is published, the citation information will be updated accordingly.

## License

This repository is distributed under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.

You are free to share and adapt the material, provided appropriate credit is given to the original source.

If you use these EOS tables, please cite the associated paper.

## Contact

For questions regarding the tables, please contact:

**P. S. Koliogiannis**  
pkoliogi@phy.hr
