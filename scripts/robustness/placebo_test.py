import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS
import warnings
warnings.filterwarnings('ignore')

np.random.seed(42)

panel = pd.read_csv('did_panel.csv', parse_dates=['week', 'treatment_date'])
control_repos = panel.loc[panel['treated'] == 0, 'repo_name'].unique()
real_treated = panel.loc[panel['treated'] == 1, 'repo_name'].unique()

print(f"Control pool to draw fake treatments from: {len(control_repos)} repos")
print(f"Number of real treated repos (matched per placebo run): {len(real_treated)}")

treat_dates = pd.read_csv('final_treated_repos.csv', parse_dates=['treatment_date'])
real_dates = treat_dates['treatment_date'].tolist()


def run_one_placebo(seed):
    rng = np.random.RandomState(seed)
    fake_treated_repos = rng.choice(control_repos, size=len(real_dates), replace=False)
    fake_dates = rng.permutation(real_dates)
    fake_treat_map = dict(zip(fake_treated_repos, fake_dates))

    # Only ever draw from real controls -- never touch real treated repos
    p = panel[panel['repo_name'].isin(control_repos)].copy()
    p['is_fake_treated'] = p['repo_name'].isin(fake_treat_map.keys())
    p['fake_treatment_date'] = p['repo_name'].map(fake_treat_map)
    p['event_time_weeks'] = ((p['week'] - p['fake_treatment_date']).dt.days / 7).round()
    p['event_quarter'] = (p['event_time_weeks'] // 13)

    treated_p = p[p['is_fake_treated']].copy()
    treated_p = treated_p[treated_p['event_quarter'].between(-8, 8)]
    control_p = p[~p['is_fake_treated']].copy()

    rp = pd.concat([treated_p, control_p], ignore_index=True)
    quarters = sorted([q for q in rp.loc[rp['is_fake_treated'] == True, 'event_quarter'].dropna().unique()])

    for q in quarters:
        if q == -1:
            continue
        qname = f"eq_{int(q)}" if q >= 0 else f"eq_m{abs(int(q))}"
        rp[qname] = ((rp['is_fake_treated'] == True) & (rp['event_quarter'] == q)).astype(int)

    dummy_cols = [c for c in rp.columns if c.startswith('eq_')]
    if len(dummy_cols) < 5:
        return None

    panel_idx = rp.set_index(['repo_name', 'week'])
    exog = panel_idx[dummy_cols].assign(const=1.0)
    endog = panel_idx['mean_log_hours']

    try:
        mod = PanelOLS(endog, exog, entity_effects=True, time_effects=True, drop_absorbed=True)
        res = mod.fit(cov_type='clustered', cluster_entity=True)
    except Exception:
        return None

    post_cols = [c for c in dummy_cols if c.startswith('eq_') and not c.startswith('eq_m')]
    n_sig = sum(1 for c in post_cols if res.pvalues.get(c, 1.0) < 0.05)
    min_p = min(res.pvalues.get(c, 1.0) for c in post_cols) if post_cols else 1.0
    return {'n_sig_post_coefs': n_sig, 'min_p_post': min_p, 'n_post_coefs': len(post_cols)}


N_PLACEBO_RUNS = 200
results = []
for i in range(N_PLACEBO_RUNS):
    r = run_one_placebo(seed=i)
    if r:
        results.append(r)
    if (i + 1) % 50 == 0:
        print(f"  ...{i+1}/{N_PLACEBO_RUNS} placebo runs done")

print(f"\nCompleted {len(results)} valid placebo runs out of {N_PLACEBO_RUNS} attempted")
df_results = pd.DataFrame(results)
print(df_results.describe())
print()
n_at_least_1 = (df_results['n_sig_post_coefs'] >= 1).sum()
n_at_least_2 = (df_results['n_sig_post_coefs'] >= 2).sum()
print(f"Runs with >=1 significant (p<0.05) post-treatment coefficient: {n_at_least_1}/{len(df_results)} ({100*n_at_least_1/len(df_results):.1f}%)")
print(f"Runs with >=2 significant coefficients: {n_at_least_2}/{len(df_results)} ({100*n_at_least_2/len(df_results):.1f}%)")

df_results.to_csv('placebo_test_results.csv', index=False)
print("\nSaved placebo_test_results.csv")