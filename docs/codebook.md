# Variable codebook for the analysis data set (`18_data_<db>.csv`)

Built by `18_build_analysis_data.py` (read-only extraction) · audited by `19_audit_join.py` · generated 12 November 2026

## Row and unit of analysis

One row is one respondent in one wave (`db` + `wave` + `id`). `(wave, id)` is unique across the file. Only the respondent-level `r` series is read from the respondent record; the `s` series (spouse information mirrored onto the respondent row) is never used. Household-level variables (`hh…`, `h…itot`) and time-invariant variables (`ragender`, `raeducl`) are used only where the construct itself is household-level or fixed.

## Identifiers and time

| Variable | Definition |
|---|---|
| `db` | mhas / hrs / share / lasi / charls |
| `wave` | harmonised wave; primary analysis uses mhas 1–6, hrs 3–16, share 1/2/5/6, lasi 1; charls 1–4 is the extension cohort |
| `year` | survey year of the wave (MHAS 2001/2003/2012/2015/2018/2021; HRS 1992+2(w−1); SHARE 2004/2007/2013/2015; LASI 2017; CHARLS 2011/2013/2015/2018) |
| `id` | cohort primary key: mhas `rahhidnp`, hrs `hhidpn`, share `mergeid`, lasi `prim_key`, charls `id`; also the cluster unit for cluster-robust standard errors |
| `iso3` | country; for SHARE, mapped from the numeric `country` code through `share_value_labels`; fixed for the other cohorts |

## Exposure

| Variable | Definition |
|---|---|
| `arth` | `r{w}arthre`, self-reported ever-diagnosed arthritis or rheumatism, 0/1. A cumulative variable (once positive it does not revert), so remission cannot be studied; it can be used to define the wave of first report. Does not distinguish osteoarthritis, rheumatoid arthritis, gout or osteoporosis |

## Amounts and deflation

| Variable | Definition |
|---|---|
| `oop_annual_lcu` | annualised nominal household out-of-pocket medical spending, local currency. HRS w3–16 originally refer to the previous two years and are divided by 2; all other cohorts use a 12-month window. Values below 0 and at or above the 999996 sentinel are dropped; 0 is a genuine zero and is retained |
| `deflator_2020` | `PPP(iso3, year) × CPI_USA(year) / CPI_USA(2020)`; World Bank WDI, `lastupdated 2026-11-11` |
| `oop_2020intl` | `oop_annual_lcu / deflator_2020`, 2020 international dollars; used for the log-OLS amount model and g-computation |
| CHARLS-specific | self-constructed total = `r{w}oopdoc1m × 12 + r{w}oophos1y + r{w}oopden1y` (dental is absent in w1/w4 and set to 0); the EOL-based harmonised total also contains **medication**, which is not available in the living-wave files, so the constructed total understates it by roughly 1–2%. **Not equivalent to the harmonised definition** |

> SHARE amounts are in national currency, so absolute amounts are not comparable across countries; the model includes country fixed effects and deflates by country-year PPP. Relative effects are invariant to any constant rescaling within a cohort.

## Income, burden and catastrophic expenditure

| Variable | Definition |
|---|---|
| `hhinc` | annual household income, local currency: mhas `h{w}itot`, hrs `h{w}itot` (stored as text, cast to numeric), share `hh1itot` (w1) / `hh{w}itothhinc` (w2/5/6), lasi `hh1itot`, charls `hh{w}itot`. Genuine negative values and large incomes are retained; amounts are not screened against the spending sentinel |
| `inc_nonpos` | flag for `hhinc <= 0`; these respondents cannot enter a ratio outcome and are described separately rather than dropped silently |
| `burden_ratio` | `oop_annual_lcu / hhinc`, defined only when `hhinc > 0` |
| `burden10` / `burden40` | indicator for `burden_ratio >= 0.10 / 0.40` (**income-based financial burden, not WHO-style catastrophic health expenditure**) |
| `ctot` | household consumption; monthly for mhas and share-w1 (multiplied by 12 when constructing the CHE indicator), annual for charls and lasi; not available in HRS |
| `che10_cons` | `oop_annual_lcu / (annualised ctot) >= 0.10`; available only for MHAS (6 waves), SHARE w1, LASI w1 and CHARLS (4 waves) |
| `miss_ctot` | consumption-missing indicator |

> **SHARE w2/w5/w6 income is not comparable with w1**: within the same respondent, `hh{w}itothhinc / hh1itot` has a median of 10.32 (w2, w6) and 10.69 (w5), which reflects a change in the variable definition rather than a change in income. The primary burden-threshold analysis therefore uses SHARE w1 only; the `/10.3178` rescaling appears in sensitivity analyses only and is not confirmed against the official codebook.

## Covariates

| Variable | Definition |
|---|---|
| `age` | age in years; primary analysis restricted to 50–110 |
| `female` | `ragender == 2` (1 = male, 2 = female) |
| `educ` | cohort-specific education codes (mhas 1–3, hrs 1–5, share 1–3, lasi 0–9, charls 1–10); entered as dummies, **levels are not compared across cohorts** |
| `married` | `mstat ∈ {1,2,3}` |
| `shlt` | self-rated health, 1 (excellent) to 5 (poor) |
| `adl_any` | `adl > 0`; mhas/share/lasi use `r{w}adla`, hrs uses `r{w}adl5a`, charls uses `r{w}adla_c` |
| `diabe` / `hibpe` / `stroke` | self-reported ever-diagnosed 0/1; the comorbidity set in the main model |
| `hearte` | heart disease 0/1; **absent from MHAS w1–3** (set to 0 with `miss_hearte`), so it is not in the main model |
| `rural` | urban/rural; **absent from HRS** (set to 0 with `miss_rural`); constant columns are dropped by the design matrix |
| `weight` / `weight_raw` | `weight` is the analysis weight normalised to a mean of 1 within each cohort × country cell; `weight_raw` is the original survey weight. CHARLS w4 carries no weight and is set to 1 |
| `flag` / `imputed` | amount-imputation flag and its binary form: mhas `flag=1`, hrs `flag>0`, share/lasi `flag ∈ {2,3,5,7}`, charls has no flag |
| `miss_*` | missing indicators for the optional covariates (rural / weight / ctot / country / hearte) |

## Exclusions already applied

- HRS w2 (the only 12-month window, 52% imputed or not self-reported) and SHARE w7 (condensed-interview flag `-4` in 63,233 records, implausible prevalence of 52.8%).
- No amount uses the `s` (spouse) series or the household-level `h2oopmd`.
- Estimation never pools individual records across cohorts: cohort-specific models are combined by DerSimonian–Laird random effects.
