import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS

# load and clean raw pr data
pr = pd.read_csv('pr_open_close_final_89repos.csv')

print("Raw shape:", pr.shape)

# Drop the rare negative-duration anomaly (PR closed "before" it opened per timestamps)
pr = pr[pr['hours_to_close'] >= 0]

# Clean merged column (comes through as string 'True'/'False'/NaN from BigQuery export)
pr['merged_clean'] = pr['merged'].map({'True': True, 'False': False}).fillna(False)

pr['opened_at'] = pd.to_datetime(pr['opened_at'])
pr['closed_at'] = pd.to_datetime(pr['closed_at'])

pr.to_csv('pr_data_clean.csv', index=False)
print("Cleaned shape:", pr.shape)

#load treatment dates, build panel
treat = pd.read_csv('final_treated_repos.csv', parse_dates=['treatment_date'])
treat_map = dict(zip(treat['repo'], treat['treatment_date']))

pr['is_treated_repo'] = pr['repo_name'].isin(treat_map.keys())
pr['treatment_date'] = pr['repo_name'].map(treat_map)
pr['log_hours_to_close'] = np.log1p(pr['hours_to_close'])

pr['week'] = pr['opened_at'].dt.to_period('W').dt.start_time

panel = pr.groupby(['repo_name', 'week']).agg(
    n_prs=('pr_number', 'count'),
    mean_log_hours=('log_hours_to_close', 'mean'),
    mean_hours=('hours_to_close', 'mean'),
    merge_rate=('merged_clean', 'mean'),
).reset_index()

panel['is_treated_repo'] = panel['repo_name'].isin(treat_map.keys())
panel['treatment_date'] = panel['repo_name'].map(treat_map)
panel['event_time_weeks'] = ((panel['week'] - panel['treatment_date']).dt.days / 7).round()
panel['post'] = np.where(panel['is_treated_repo'], (panel['week'] >= panel['treatment_date']).astype(int), 0)
panel['treated'] = panel['is_treated_repo'].astype(int)
panel['treated_x_post'] = panel['treated'] * panel['post']

panel.to_csv('did_panel.csv', index=False)
print("Panel shape:", panel.shape)
print("Treated repos:", panel.loc[panel['treated']==1, 'repo_name'].nunique())
print("Control repos:", panel.loc[panel['treated']==0, 'repo_name'].nunique())

#build event-quarter dummies (Sun-Abraham), quarter -1 = reference
treated_panel = panel[panel['treated'] == 1].copy()
control_panel = panel[panel['treated'] == 0].copy()

treated_panel['event_quarter'] = (treated_panel['event_time_weeks'] // 13)

# Drop (not clip!) observations outside +/-8 quarters -- clipping would wrongly
# bloat the endpoint bins with all the more-extreme observations
before = len(treated_panel)
treated_panel = treated_panel[treated_panel['event_quarter'].between(-8, 8)]
print(f"Dropped {before - len(treated_panel)} treated obs outside +/-8 quarter window")

reg_panel = pd.concat([treated_panel, control_panel], ignore_index=True)
reg_panel['event_quarter'] = reg_panel['event_quarter'].fillna(-999)

quarters = sorted([q for q in reg_panel.loc[reg_panel['treated']==1, 'event_quarter'].unique()])
for q in quarters:
    if q == -1:
        continue  # reference category, omitted
    qname = f"eq_{int(q)}" if q >= 0 else f"eq_m{abs(int(q))}"
    reg_panel[qname] = ((reg_panel['treated'] == 1) & (reg_panel['event_quarter'] == q)).astype(int)

dummy_cols = [c for c in reg_panel.columns if c.startswith('eq_')]
reg_panel.to_csv('reg_panel_with_dummies.csv', index=False)
print("Event-quarter dummy columns:", dummy_cols)

#run the event-study regression (repo FE + calendar-week FE, clustered SEs)
panel_idx = reg_panel.set_index(['repo_name', 'week'])
exog = panel_idx[dummy_cols].assign(const=1.0)
endog = panel_idx['mean_log_hours']

mod = PanelOLS(endog, exog, entity_effects=True, time_effects=True, drop_absorbed=True)
res = mod.fit(cov_type='clustered', cluster_entity=True)

print()
print(res.summary)

with open('panelols_summary.txt', 'w') as f:
    f.write(str(res.summary))
print("\nDone. Full summary saved to panelols_summary.txt")