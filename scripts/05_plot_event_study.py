import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from linearmodels.panel import PanelOLS

panel = pd.read_csv('reg_panel_with_dummies.csv', parse_dates=['week'])
dummy_cols = [c for c in panel.columns if c.startswith('eq_')]

panel_idx = panel.set_index(['repo_name', 'week'])
exog = panel_idx[dummy_cols].assign(const=1.0)
endog = panel_idx['mean_log_hours']

mod = PanelOLS(endog, exog, entity_effects=True, time_effects=True, drop_absorbed=True)
res = mod.fit(cov_type='clustered', cluster_entity=True)

# Build ordered series: quarters -8..-2, then reference quarter -1 (coef=0), then 0..8
order = ['eq_m8','eq_m7','eq_m6','eq_m5','eq_m4','eq_m3','eq_m2']
order += ['eq_0','eq_1','eq_2','eq_3','eq_4','eq_5','eq_6','eq_7','eq_8']
quarter_labels = [-8,-7,-6,-5,-4,-3,-2, 0,1,2,3,4,5,6,7,8]

coefs = [res.params[c] for c in order]
ci_lower = [res.conf_int().loc[c, 'lower'] for c in order]
ci_upper = [res.conf_int().loc[c, 'upper'] for c in order]

# Insert the omitted reference quarter -1 (coefficient defined as 0, no CI) right before quarter 0
quarter_labels.insert(7, -1)
coefs.insert(7, 0.0)
ci_lower.insert(7, 0.0)
ci_upper.insert(7, 0.0)

fig, ax = plt.subplots(figsize=(10, 6))
ax.axhline(0, color='gray', linewidth=0.8, linestyle='-')
ax.axvline(-0.5, color='red', linewidth=1, linestyle='--', label='Treatment (CODEOWNERS introduced)')

ax.errorbar(quarter_labels, coefs,
            yerr=[np.array(coefs) - np.array(ci_lower), np.array(ci_upper) - np.array(coefs)],
            fmt='o-', color='#2c3e50', ecolor='#7f8c8d', elinewidth=1.5, capsize=3, markersize=5)

ax.set_xlabel('Quarters relative to CODEOWNERS introduction')
ax.set_ylabel('Effect on log(hours to close PR)\n(relative to quarter -1)')
ax.set_title('Event-Study: Effect of CODEOWNERS Introduction on PR Closing Time')
ax.legend(loc='upper left')
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('event_study_plot.png', dpi=150)
print("Saved event_study_plot.png in the current folder")