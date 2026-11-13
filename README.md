# arthritis-oop-spending

Analysis code for a multi-cohort study of **self-reported arthritis and household
out-of-pocket (OOP) medical spending** in four harmonised ageing cohorts
(HRS, SHARE, MHAS, LASI; 25 waves; 576,020 person-waves), with CHARLS retained as an
extension cohort.

The study estimates (i) the probability of any OOP spending, (ii) the amount among
spenders, using a two-part model with cohort-specific estimation and DerSimonian–Laird
random-effects synthesis, and (iii) the composition, timing and cross-country
consistency of the excess, plus socioeconomic effect modification.

**This repository contains code only.** No respondent-level or household-level data
are included, and none can be redistributed. See *Data* below.

---

## Data

All input data come from the [Gateway to Global Aging Data](https://g2aging.org/)
harmonised files and the original cohort programmes:

| Cohort | Provider | Access |
|---|---|---|
| HRS | University of Michigan | registration + data-use agreement |
| SHARE | SHARE-ERIC | registration + data-use agreement |
| MHAS | University of Texas / INEGI | registration |
| LASI | University of Southern California / IIPS | registration |
| CHARLS | Peking University | registration |

The harmonised files were loaded into a local PostgreSQL instance, one database per
cohort (`hrs`, `share`, `mhas`, `lasi`, `charls`, …), keeping the table names used by
the Gateway distribution (for example `h_mhas_d_p3`, `randhrs1992_2022v1_p7`,
`gh_share_p4`). Only the respondent-level `r` variable series is used; the `s`
(spouse-mirror) series is excluded throughout.

Because access is governed by data-use agreements, the scripts assume the databases
already exist locally. They are read-only: every query is a `SELECT`.

## Requirements

- Python 3.10+
- PostgreSQL 13+ with the harmonised cohort files loaded
- Python packages: `psycopg2-binary`, `pandas`, `numpy`, `scipy`, `statsmodels`,
  `Pillow`, `svglib`, `reportlab`, `PyMuPDF`

```bash
pip install psycopg2-binary pandas numpy scipy statsmodels Pillow svglib reportlab PyMuPDF
```

## Configuration

No credentials are stored in this repository. Connection settings are read from the
environment:

| Variable | Default | Meaning |
|---|---|---|
| `OOPE_DB_HOST` | `localhost` | PostgreSQL host |
| `OOPE_DB_PORT` | `5432` | PostgreSQL port |
| `OOPE_DB_USER` | `postgres` | database user |
| `OOPE_DB_PASSWORD` | *(empty)* | database password |
| `OOPE_OUT_DIR` | `<repo>/outputs` | directory for all derived tables and logs |
| `OOPE_RDATA_DIRS` | *(empty)* | `os.pathsep`-separated list of directories holding the raw `.dta` files (only used by `03_var_exact.py`) |

```bash
export OOPE_DB_PASSWORD='...'
python analysis/11_feasibility_main.py
```

## Pipeline

Scripts keep their original numbering so that they can be matched to the script
indices reported in the paper. Run them in the order below; each writes its outputs
to `$OOPE_OUT_DIR`.

| Step | Scripts | Purpose |
|---|---|---|
| 1. Variable discovery | `01`, `03`, `05`, `07`–`10` | locate OOP, arthritis and covariate variables and their wave coverage in the harmonised files |
| 2. Feasibility | `11` | wave-by-wave OOP distributions, arthritis cell sizes, imputation flags |
| 3. Components and thresholds | `12`, `14`, `15` | inpatient/outpatient/drug components; income-denominated burden thresholds |
| 4. Covariates and deflators | `16`, `17`, `17b` | covariate availability; World Bank PPP and CPI extracts |
| 5. Analysis data set | `18`, `19` | build the person-wave analysis file; audit the joins and row counts |
| 6. Main two-part model | `20`, `21`, `22` | probability of any OOP; amount among spenders; forest and sensitivity tables |
| 7. Composition (A2) | `23`, `24`, `29` | component shares; meta-analysis of component amount ratios; closure to the cohort totals |
| 8. Timing (A3) | `25`, `26` | event-study panel around the wave of first reported arthritis; descriptive trajectory |
| 9. Cross-country consistency (A4) | `27`, `28`, `35` | country-level institutional context; ecological meta-regression; leave-one-out and strata checks |
| 10. Effect modification | `41` | income-quintile and education stratification; interaction tests with BH-FDR control |
| 11. Diagnostics | `30`, `31`, `32` | MHAS wave-gap check; reversal of the 40% threshold after adjustment; SHARE income-definition check |
| 12. Figures | `33`, `34`, `36` | five publication figures; value validation; TIFF/EPS/PDF/SVG export |

## Outputs

All derived files land in `$OOPE_OUT_DIR` (git-ignored): result tables (`*.csv`),
run logs (`*.txt`, `*.log`) and machine-readable summaries (`*.json`).

## What is intentionally not included

- **Respondent-level data.** No `.csv`, `.dta`, `.rds` or database dump. The scripts
  read from your own local copy of the harmonised files.
- **Manuscript and submission tooling.** The manuscript builder, the reference
  renumbering and verification utilities, the table/figure packaging scripts and the
  declarations cross-check are part of the submission workflow and embed unpublished
  text; they are not analysis code and are not published here.
- **Intermediate results.** Every table and figure is regenerated by the pipeline
  above from the source databases.

## Citation

If you use this code, please cite the article (full reference to be added on
publication) and this repository. A versioned archive with a DOI will be deposited
in Zenodo; the DOI will be added here once minted.

## License

MIT — see `LICENSE`.
