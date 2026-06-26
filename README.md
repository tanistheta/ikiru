# Ikiru: Does CODEOWNERS Adoption Change How Fast Pull Requests Get Closed?

A staggered-adoption difference-in-differences study of GitHub's `CODEOWNERS`
governance feature, using ~21TB of GH Archive data.

> **Status:** Core analysis complete. Headline result: no significant effect
> on PR closing time through ~18 months post-adoption. A late-window signal
> (months 20–24) is real but not yet causally attributable — see
> [Limitations](#limitations).

---

## Table of Contents

- [Research Question](#research-question)
- [Why This Matters](#why-this-matters)
- [Data and Sample](#data-and-sample)
- [Method](#method)
- [Results](#results)
- [Robustness Checks](#robustness-checks)
- [Heterogeneity by CODEOWNERS Coverage](#heterogeneity-by-codeowners-coverage)
- [Comparison to Related Work](#comparison-to-related-work)
- [Limitations](#limitations)
- [Repository Structure](#repository-structure)
- [Reproducing This Study](#reproducing-this-study)
- [References](#references)

---

## Research Question

In 2017, GitHub introduced `CODEOWNERS`: a configuration file that
automatically assigns required reviewers to pull requests touching specific
files or directories. It is a deliberate, low-friction governance
mechanism — but does adopting it actually change anything observable about
how a project's pull requests get processed?

This study asks one specific, narrow version of that question:

> **Does introducing a `CODEOWNERS` file cause a measurable change in how
> long pull requests stay open before being closed?**

## Why This Matters

Code ownership policy sits at the intersection of software governance,
supply-chain security, and day-to-day developer workflow. GitHub frames
`CODEOWNERS` as a way to "strengthen accountability and streamline the
review process." Most evidence for that claim, until recently, has been
anecdotal. This study — alongside the concurrently published
[Lulla, Kula & Treude (2025)](#references) — is part of a small but growing
body of causal, large-scale empirical work trying to test that claim
directly rather than take it on faith.

## Data and Sample

- **Source:** GH Archive, queried via Google BigQuery (~21TB scanned across
  the full table history).
- **Outcome data window:** 2021-01-01 to 2026-03-31.
- **Repository pool:** Built independently of `CODEOWNERS` adoption status —
  top-starred, actively-maintained repositories (pushed to since January
  2024) sampled across 12 major languages via the GitHub Search API — to
  avoid selection bias from searching specifically for repos known to have
  the file.
- **Treated group:** 28 repositories that introduced a `CODEOWNERS` file
  between January 2021 and March 2026, with exact treatment dates identified
  from GitHub's commit history (date-level precision, not inferred).
- **Control group:** 60 repositories that never adopted `CODEOWNERS` (later
  reduced to 42 after a balance correction — see
  [Robustness Checks](#robustness-checks)).
- **Outcome variable:** PR closing time in hours, log-transformed
  (`log(1 + hours)`) to address right-skew, aggregated to repository-week
  cells (`mean_log_hours`).

**Why closing time, not review latency.** The more direct outcome —
time-to-first-review — relies on `PullRequestReviewEvent`, whose GH Archive
coverage is unreliable before ~2022. Using it would have shrunk the usable
treated set to 3 repositories or forced a much narrower time window. PR
closing time (open → closed) is an imperfect proxy — it conflates review
speed with unrelated factors like release freezes — but it is available
reliably across the full 2021–2026 window. This trade-off is treated as a
core, accepted limitation, not a footnote.

## Method

Because the 28 treated repositories adopted `CODEOWNERS` at different
calendar dates, naive two-way fixed effects (TWFE) regression is known to
produce biased estimates under staggered adoption with heterogeneous
treatment effects (Goodman-Bacon, 2021; Sun & Abraham, 2021; Callaway &
Sant'Anna, 2021). This study uses a **Sun-Abraham-style event-study design**:

- Event-time dummies relative to each repository's own treatment date
  (quarters −8 to +8, with quarter −1 as the omitted reference period).
- Repository fixed effects (absorb each repo's baseline level).
- Calendar-quarter fixed effects (absorb shocks common to all repos,
  treated and control alike).
- Standard errors clustered at the repository level.

## Results

![Event-study plot: effect of CODEOWNERS introduction on PR closing time](./assets/event_study_plot.png)

**No statistically significant effect at any horizon from −8 to +8 quarters.**
Pre-trends are flat (all pre-period coefficients insignificant, supporting
the design's internal validity). Coefficients at quarters +7 and +8 drift
upward (β ≈ 0.38–0.40) but remain short of conventional significance
(p ≈ 0.09–0.11).

A monthly-bin robustness check surfaces two significant coefficients at
months 23–24 post-adoption (p = 0.0277 and p = 0.0445). This is investigated
in detail below rather than reported as a clean finding — see
[Limitations](#limitations).

## Robustness Checks

| Check | Result |
|---|---|
| **Placebo test** (200 iterations, fake treatment dates randomly assigned among genuine controls only) | 0 significant post-treatment coefficients in 69.5% of runs — consistent with chance under a true null. The 20–24 month signal's strength (2 significant coefficients) occurred in **12.5%** of placebo runs by chance alone, meaning it is plausible as noise. |
| **Control-group balance check** | Treated repos had ~2.5–3× the PR volume of controls (p = 0.001). Resolved by dropping 18 low-activity controls below the treated group's own 10th percentile (60 → 42 controls). Re-running the main regression on the rebalanced panel changed every coefficient by <0.02 in absolute terms — the imbalance was real but not distorting the result. |
| **`react/react` data gap** | Investigated, not silently dropped: GH Archive logs `repo.name` at time-of-event, and the repo migrated from `facebook/react` mid-window, so historical PRs are filed under the old name. A fix exists but was not run — it would re-scan the full 5-year window at the original ~$127 cost to recover one control out of 60, a poor trade. Documented as a deliberate, costed decision. |

### The month 23–24 signal, diagnosed

Only 17 of the 28 treated repositories are old enough (treated by ~March
2024) to have any observations at month 23–24 given the panel's March 2026
cutoff. Within that cohort, mean `mean_log_hours` rises from 2.38
(pre-treatment baseline) to 2.76 (month 24) — a real, broad-based shift
across most of the 17 contributing repos, not an artifact of one outlier.

However, this is a comparison of the **same 17 early-adopting repos to
themselves**, late in calendar time versus early in calendar time. Repository
and time fixed effects cannot separate "these repos changed as they matured"
from "CODEOWNERS had a delayed effect," because no later-adopting cohort
exists yet at the same post-treatment horizon to net the maturation effect
out against. Combined with the 12.5% placebo-chance rate above, this signal
is reported as **real and broad-based, but not yet causally separable from
cohort-specific change** — and should be re-checked as the 2024–2026 adopter
cohort (Llama.cpp, Transformers, Bun, Kotlin, Homebrew, Dify, and others)
ages into its own 18–24 month window in future data.

## Heterogeneity by CODEOWNERS Coverage

Motivated by Lulla et al.'s finding of a bimodal coverage distribution
(≤10% vs ≥90% of files protected), treated repos were split into low/high
coverage buckets and the regression re-run separately on each.

| Bucket | n (treated) | Pre-trends | Late-window result |
|---|---|---|---|
| **Low coverage (≤10%)** | 14 | Clean, flat, insignificant | Reproduces the main finding: eq_7 p=0.087, eq_8 p=0.022 |
| **High coverage (≥90%)** | 8 | **Significant pre-treatment coefficients** (parallel-trends violation) | Not interpretable — underpowered, not evidence of a differential effect |

The honest conclusion: the larger, well-identified low-coverage subset
confirms the pooled result. The high-coverage subset cannot currently
support a heterogeneity claim — this is a data limitation (n=8, skewed
toward recently-popular AI-tooling repos with idiosyncratic pre-period
activity), not a finding that coverage doesn't matter.

## Comparison to Related Work

A directly comparable study — [Lulla, Kula & Treude (2025)](#references) —
was published in December 2025 using Regression Discontinuity Design (RDD)
on 222 repositories (844K+ PRs). The two studies ask closely related but
not identical questions, using different causal designs:

| | This study | Lulla, Kula & Treude (2025) |
|---|---|---|
| Causal design | Staggered DiD, panel with entity + time FE | RDD, per-repo local linear regression |
| Scale | 89 repos (70 after balance correction); ~13,700 repo-weeks | 222 repos; 844,492 PRs |
| Outcome | PR closing time | PR merge time, comment count, reviewer count |
| Time horizon | Asymmetric, staggered, up to ±24 months | Fixed, symmetric ±12 months |
| Control group | Not-yet-treated repos (within-panel) | Both never-adopters and pre-period of adopters |
| Robustness | Placebo test, balance check | Not reported |

**Where they agree:** both find the effect is small and statistically
fragile for most individual repositories — Lulla et al. report that
~65% of their 222 repos show no significant change at α = 0.05, consistent
with this study's largely null result.

**Where this study extends theirs:** the staggered design observes up to 24
months post-adoption; Lulla et al.'s fixed 12-month RDD window cannot
detect an effect (real or spurious) that emerges later, by construction.
The month 23–24 signal found here sits entirely outside their design's
observable range — it is a genuine extension of the observation window, even
though it cannot yet be attributed to CODEOWNERS with confidence.

## Limitations

1. **Closing time is not review latency.** The largest interpretive caveat —
   a null result here does not rule out an effect on review thoroughness.
2. **Small per-cohort sample sizes.** Individual event-time bins are
   supported by 13–23 distinct repositories.
3. **Thin post-treatment windows for the latest adopters.** `zed-industries/zed`
   and `openclaw/openclaw` have only 6 and 2 weeks of post-treatment data
   respectively.
4. **The month 20–24 signal is cohort-confounded**, as detailed above —
   real and broad-based, but not yet separable from organic cohort
   maturation without a later-adopting comparison group at the same horizon.
5. **No causal claim about mechanism.** This design cannot distinguish
   `CODEOWNERS` itself from other simultaneous governance changes at the
   same repositories.
6. **Generalizability.** Restricted to highly-starred, actively-maintained,
   primarily English-language open-source projects across a specific set
   of languages.
7. **One control repo (`react/react`) is missing from outcome data** —
   investigated and documented as a deliberate, costed decision not to fix
   (see Robustness Checks).
8. **Coverage-based heterogeneity is inconclusive** for the high-coverage
   subset due to a parallel-trends violation in a small (n=8) sample.

## Repository Structure

```
.
├── README.md
├── .gitignore
├── scripts/
│   ├── 01_expand_repo_pool.py            # builds the candidate repo pool
│   ├── 02_find_codeowners_date.py        # identifies exact treatment dates via GitHub API
│   ├── 03_build_did_panel.py             # constructs the repo-week panel
│   ├── 04_compute_codeowners_coverage.py # per-repo CODEOWNERS file coverage %
│   ├── 05_plot_event_study.py            # generates the event-study figure
│   └── robustness/
│       ├── balance_check_and_rerun.py    # control-group balance diagnostic + re-run
│       ├── placebo_test.py               # 200-iteration placebo test
│       ├── robustness_monthly.py         # monthly-bin robustness regression
│       └── heterogeneity_by_coverage.py  # split-sample regression by coverage bucket
├── data/
│   ├── raw/            # gitignored — large BigQuery pulls, regenerable
│   │   ├── pr_data_clean.csv
│   │   ├── pr_open_close_2021_2026.csv
│   │   └── repo_activity_summary.csv
│   ├── pipeline/       # gitignored — intermediate pool/date-discovery files
│   │   ├── expanded_pool_clean.csv
│   │   ├── expanded_pool_excluded.csv
│   │   ├── expanded_codeowners_dates.csv
│   │   ├── expanded_codeowners_dates_round2.csv
│   │   └── codeowners_treatment_dates.csv
│   └── final/          # tracked — needed to verify/rerun the analysis
│       ├── final_treated_repos.csv
│       ├── pr_open_close_final_89repos.csv
│       ├── did_panel.csv
│       ├── reg_panel_monthly.csv
│       ├── reg_panel_with_dummies.csv
│       ├── codeowners_coverage.csv
│       └── controls_to_drop_for_balance.txt
└── results/
    ├── figures/
    │   └── event_study_plot.png
    └── summaries/
        ├── panelols_summary.txt
        ├── panelols_balanced_summary.txt
        ├── robustness_monthly_summary.txt
        ├── heterogeneity_low_summary.txt
        ├── heterogeneity_high_summary.txt
        └── placebo_test_results.csv
```

`data/raw/` and `data/pipeline/` are excluded from version control (see
`.gitignore`) since they're large and fully regenerable from the scripts in
order — only `data/final/` and `results/` are tracked, since those are what's
needed to verify or extend the analysis without redoing the BigQuery scan.

## Reproducing This Study

1. **Build the repo pool and identify treatment dates** — requires a
   GitHub personal access token (`GITHUB_TOKEN` env var; never commit this):
   ```bash
   python scripts/01_expand_repo_pool.py
   python scripts/02_find_codeowners_date.py
   ```
2. **Pull outcome data from GH Archive via BigQuery** — note this scans
   the full table history (~21TB); budget accordingly.
3. **Build the panel**:
   ```bash
   pip install pandas linearmodels
   python scripts/03_build_did_panel.py
   ```
4. **Run robustness checks**:
   ```bash
   python scripts/robustness/placebo_test.py
   python scripts/robustness/balance_check_and_rerun.py
   python scripts/robustness/robustness_monthly.py
   ```
5. **Run the coverage heterogeneity check** (requires `GITHUB_TOKEN`):
   ```bash
   python scripts/04_compute_codeowners_coverage.py
   python scripts/robustness/heterogeneity_by_coverage.py
   ```
6. **Regenerate the figure**:
   ```bash
   python scripts/05_plot_event_study.py
   ```


## References

Lulla, J. L., Kula, R. G., & Treude, C. (2025). *Automated Code Review
Assignments: An Alternative Perspective of Code Ownership on GitHub.*
arXiv:2512.05551 [cs.SE]. https://arxiv.org/abs/2512.05551

Goodman-Bacon, A. (2021). Difference-in-differences with variation in
treatment timing. *Journal of Econometrics*, 225(2), 254–277.

Sun, L., & Abraham, S. (2021). Estimating dynamic treatment effects in event
studies with heterogeneous treatment effects. *Journal of Econometrics*,
225(2), 175–199.

Callaway, B., & Sant'Anna, P. H. C. (2021). Difference-in-differences with
multiple time periods. *Journal of Econometrics*, 225(2), 200–230.