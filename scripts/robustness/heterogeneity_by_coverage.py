import pandas as pd
from linearmodels.panel import PanelOLS

PANEL_PATH = "did_panel.csv"
COVERAGE_PATH = "codeowners_coverage.csv"


def load_data():
    did = pd.read_csv(PANEL_PATH, parse_dates=["week"])
    cov = pd.read_csv(COVERAGE_PATH)[["repo", "coverage_bucket"]].rename(
        columns={"repo": "repo_name"}
    )
    did = did.merge(cov, on="repo_name", how="left")
    did["treatment_date"] = pd.to_datetime(did["treatment_date"])
    return did


def build_event_time(did):
    treated_mask = did["is_treated_repo"] == True
    did.loc[treated_mask, "event_q"] = (
        (did.loc[treated_mask, "week"] - did.loc[treated_mask, "treatment_date"]).dt.days
        / 91.25
    ).round()
    did["event_q"] = did["event_q"].clip(-8, 8)
    return did


def run_split(did, cov_lookup, bucket_name, label):
    sub_repos = cov_lookup.loc[
        cov_lookup["coverage_bucket"] == bucket_name, "repo_name"
    ].tolist()
    control_repos = did.loc[did["is_treated_repo"] == False, "repo_name"].unique().tolist()

    panel = did[did["repo_name"].isin(sub_repos + control_repos)].copy()
    panel = panel.dropna(subset=["mean_log_hours"])

    panel["eq"] = panel["event_q"]
    dummies = pd.get_dummies(panel["eq"], prefix="eq", dummy_na=False)
    ref_col = [c for c in dummies.columns if c.endswith("-1.0")]
    if ref_col:
        dummies = dummies.drop(columns=ref_col)
    panel = pd.concat([panel, dummies], axis=1)
    panel = panel.set_index(["repo_name", "week"])
    dummy_cols = list(dummies.columns)

    print(f"\n=== {label} (n_repos_treated={len(sub_repos)}) ===")
    print(f"Repos: {sub_repos}")

    try:
        mod = PanelOLS(
            panel["mean_log_hours"],
            panel[dummy_cols],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        res = mod.fit(cov_type="clustered", cluster_entity=True)
        print(res)

        out_path = f"heterogeneity_{bucket_name}_summary.txt"
        with open(out_path, "w") as f:
            f.write(f"{label} (n_repos_treated={len(sub_repos)})\n")
            f.write(f"Repos: {sub_repos}\n\n")
            f.write(str(res))
        print(f"\nWrote {out_path}")

        # Quick pre-trend flag: check if any eq_-N coefficient (N >= 4) is
        # significant at p<0.05, which would indicate a parallel-trends
        # violation rather than a clean pre-period.
        pre_cols = [c for c in dummy_cols if c.startswith("eq_-")]
        sig_pre = [c for c in pre_cols if res.pvalues.get(c, 1.0) < 0.05]
        if sig_pre:
            print(
                f"\n  WARNING: significant pre-treatment coefficient(s) found: "
                f"{sig_pre}. This indicates a parallel-trends violation for "
                f"this subgroup; treat results for this bucket as unreliable, "
                f"not as evidence of a differential effect."
            )
        else:
            print("\n  Pre-trends clean (no significant pre-period coefficients).")

        return res
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def main():
    did = load_data()
    did = build_event_time(did)
    cov_lookup = pd.read_csv(COVERAGE_PATH)[["repo", "coverage_bucket"]].rename(
        columns={"repo": "repo_name"}
    )

    print("Coverage bucket counts:")
    print(cov_lookup["coverage_bucket"].value_counts(dropna=False))

    run_split(did, cov_lookup, "low", "LOW COVERAGE (<=10%)")
    run_split(did, cov_lookup, "high", "HIGH COVERAGE (>=90%)")


if __name__ == "__main__":
    main()