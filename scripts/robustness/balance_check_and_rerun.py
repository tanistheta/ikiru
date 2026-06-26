import pandas as pd
import numpy as np
from scipy import stats
from linearmodels.panel import PanelOLS

#per-repo activity summary
pr = pd.read_csv('pr_open_close_final_89repos.csv')
treat = pd.read_csv('final_treated_repos.csv', parse_dates=['treatment_date'])
treated_repos = set(treat['repo'])

pr['opened_at'] = pd.to_datetime(pr['opened_at'])

summary = pr.groupby('repo_name').agg(
    n_prs=('pr_number', 'count'),
    first_pr=('opened_at', 'min'),
    last_pr=('opened_at', 'max'),
).reset_index()
summary['is_treated'] = summary['repo_name'].isin(treated_repos)
summary['span_days'] = (summary['last_pr'] - summary['first_pr']).dt.days
summary['prs_per_week'] = summary['n_prs'] / (summary['span_days'] / 7).replace(0, np.nan)

print("Activity comparison, treated vs control:")
print(summary.groupby('is_treated')['n_prs'].describe())
print()

t_stat, p_val = stats.ttest_ind(
    np.log1p(summary.loc[summary['is_treated'], 'n_prs']),
    np.log1p(summary.loc[~summary['is_treated'], 'n_prs']),
    equal_var=False
)
print(f"T-test on log(1+n_prs) BEFORE filtering: t={t_stat:.3f}, p={p_val:.4f}")
summary.to_csv('repo_activity_summary.csv', index=False)

#drop low-activity controls using treated group's own 10th percentile
treated_p10 = summary[summary['is_treated']]['n_prs'].quantile(0.1)
print(f"\nFloor = treated group's 10th percentile = {treated_p10:.0f} PRs")

dropped_controls = summary[(~summary['is_treated']) & (summary['n_prs'] < treated_p10)]
print(f"Dropping {len(dropped_controls)} low-activity controls:")
print(dropped_controls[['repo_name', 'n_prs']].sort_values('n_prs').to_string(index=False))

with open('controls_to_drop_for_balance.txt', 'w') as f:
    f.write(f"Controls dropped for activity-level balance (threshold = treated group's 10th percentile, {treated_p10:.0f} PRs):\n")
    for r in dropped_controls['repo_name']:
        f.write(f"{r}\n")
print("\nSaved controls_to_drop_for_balance.txt")

# Re-check balance after filtering
filtered = summary[~summary['repo_name'].isin(dropped_controls['repo_name'])]
t_stat2, p_val2 = stats.ttest_ind(
    np.log1p(filtered[filtered['is_treated']]['n_prs']),
    np.log1p(filtered[~filtered['is_treated']]['n_prs']),
    equal_var=False
)
print(f"\nT-test on log(1+n_prs) AFTER filtering: t={t_stat2:.3f}, p={p_val2:.4f}")

#re-run the main regression on the rebalanced panel
reg_panel = pd.read_csv('reg_panel_with_dummies.csv', parse_dates=['week'])
print(f"\nBefore drop: {reg_panel['repo_name'].nunique()} repos, {len(reg_panel)} obs")

dropped_set = set(dropped_controls['repo_name'])
reg_panel = reg_panel[~reg_panel['repo_name'].isin(dropped_set)]
print(f"After drop: {reg_panel['repo_name'].nunique()} repos, {len(reg_panel)} obs")

dummy_cols = [c for c in reg_panel.columns if c.startswith('eq_')]
panel_idx = reg_panel.set_index(['repo_name', 'week'])
exog = panel_idx[dummy_cols].assign(const=1.0)
endog = panel_idx['mean_log_hours']

mod = PanelOLS(endog, exog, entity_effects=True, time_effects=True, drop_absorbed=True)
res = mod.fit(cov_type='clustered', cluster_entity=True)

print()
print(res.summary)

with open('panelols_balanced_summary.txt', 'w') as f:
    f.write(str(res.summary))
print("\nDone. Saved panelols_balanced_summary.txt")