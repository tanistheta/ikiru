import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS

# Reuse the already-cleaned PR data and treatment dates
pr = pd.read_csv('pr_open_close_final_89repos.csv')
pr = pr[pr['hours_to_close'] >= 0]
pr['merged_clean'] = pr['merged'].map({'True': True, 'False': False}).fillna(False)
pr['opened_at'] = pd.to_datetime(pr['opened_at'])
pr['closed_at'] = pd.to_datetime(pr['closed_at'])

treat = pd.read_csv('final_treated_repos.csv', parse_dates=['treatment_date'])
treat_map = dict(zip(treat['repo'], treat['treatment_date']))

pr['is_treated_repo'] = pr['repo_name'].isin(treat_map.keys())
pr['treatment_date'] = pr['repo_name'].map(treat_map)
pr['log_hours_to_close'] = np.log1p(pr['hours_to_close'])

# Aggregate to repo-MONTH level this time (finer than the original repo-week)
pr['month'] = pr['opened_at'].dt.to_period('M').dt.start_time

panel = pr.groupby(['repo_name', 'month']).agg(
    n_prs=('pr_number', 'count'),
    mean_log_hours=('log_hours_to_close', 'mean'),
).reset_index()

panel['is_treated_repo'] = panel['repo_name'].isin(treat_map.keys())
panel['treatment_date'] = panel['repo_name'].map(treat_map)
panel['event_time_months'] = ((panel['month'] - panel['treatment_date']).dt.days / 30.44).round()
panel['treated'] = panel['is_treated_repo'].astype(int)

treated_panel = panel[panel['treated'] == 1].copy()
control_panel = panel[panel['treated'] == 0].copy()

# Cap window at +/-24 months (~2 years, matching the +/-8 quarter window from before)
before = len(treated_panel)
treated_panel = treated_panel[treated_panel['event_time_months'].between(-24, 24)]
print(f"Dropped {before - len(treated_panel)} treated obs outside +/-24 month window")

reg_panel = pd.concat([treated_panel, control_panel], ignore_index=True)
reg_panel['event_time_months'] = reg_panel['event_time_months'].fillna(-999)

months = sorted([m for m in reg_panel.loc[reg_panel['treated']==1, 'event_time_months'].unique()])
for m in months:
    if m == -1:
        continue  # reference category
    mname = f"em_{int(m)}" if m >= 0 else f"em_m{abs(int(m))}"
    reg_panel[mname] = ((reg_panel['treated'] == 1) & (reg_panel['event_time_months'] == m)).astype(int)

dummy_cols = [c for c in reg_panel.columns if c.startswith('em_')]
print(f"Built {len(dummy_cols)} monthly event-time dummies")

reg_panel.to_csv('reg_panel_monthly.csv', index=False)

panel_idx = reg_panel.set_index(['repo_name', 'month'])
exog = panel_idx[dummy_cols].assign(const=1.0)
endog = panel_idx['mean_log_hours']

mod = PanelOLS(endog, exog, entity_effects=True, time_effects=True, drop_absorbed=True)
res = mod.fit(cov_type='clustered', cluster_entity=True)

print()
print(res.summary)

with open('robustness_monthly_summary.txt', 'w') as f:
    f.write(str(res.summary))
print("\nSaved robustness_monthly_summary.txt")