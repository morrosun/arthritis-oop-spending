# -*- coding: utf-8 -*-
"""方向 A / 1a 定稿：主结局 = P1(有无自付) + P2inc(控制收入后的有支出者金额比)。
B10/B40 降为次要结局；消费 CHE 与 CHARLS 为敏感性/扩展，不并入主 meta。
只读已有 CSV，不重跑模型、不连库。
输出：22_1a_main_table.csv / 22_1a_secondary_table.csv /
      22_1a_sensitivity_table.csv / 22_1a_forest.csv /
      22_1a_gcomp.csv / 22_1a_final.txt / 22_1a_manuscript_numbers.md
"""
import os, pandas as pd, numpy as np
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(os.path.join(OUT, '22_1a_final.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

R20 = pd.read_csv(os.path.join(OUT, '20_a1_main_results.csv'))
M20 = pd.read_csv(os.path.join(OUT, '20_a1_meta.csv'))
G   = pd.read_csv(os.path.join(OUT, '20_a1_gcomp.csv'))
S   = pd.read_csv(os.path.join(OUT, '21_a1_revised_sensitivity.csv'))
MS  = pd.read_csv(os.path.join(OUT, '21_a1_revised_meta.csv'))
T1  = pd.read_csv(os.path.join(OUT, '20_table1.csv'))
MAIN = ['mhas','hrs','share','lasi']

log("方向 A / 1a 定稿｜" + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
log("主结局：P1_any_oop（OR）+ P2inc_amount_log_adj_income（金额比，控制 log 收入）")
log("次要结局：B10/B40 income-based financial burden；P2_amount_log 作对照")
log("不并入主 meta：消费 CHE（可得子样本）、CHARLS（自建总额）、SHARE 收入经验校正版\n")

def meta_row(set_, oc):
    q = MS[(MS['set']==set_) & (MS['outcome']==oc)]
    return q.iloc[0].to_dict() if len(q) else {}

def db_row(set_, db, oc):
    q = S[(S['set']==set_) & (S['db']==db) & (S['outcome']==oc)]
    return q.iloc[0].to_dict() if len(q) else {}

PRIMARY = [('P1_any_oop', 'OR', '有无自付支出'),
           ('P2inc_amount_log_adj_income', '金额比', '有支出者年化自付金额（控制 log 家庭收入）')]
SECOND  = [('B10_oop_ge10pct_income', 'OR', 'OOP/家庭收入 >=10%'),
           ('B40_oop_ge40pct_income', 'OR', 'OOP/家庭收入 >=40%'),
           ('P2_amount_log', '金额比', '有支出者金额（未控制收入，对照）')]

rows, forest = [], []
for oc, unit, label in PRIMARY + SECOND:
    tier = 'primary' if oc in [x[0] for x in PRIMARY] else 'secondary'
    m = meta_row('main_revised', oc)
    for db in MAIN:
        r = db_row('main_revised', db, oc)
        if not r: continue
        rows.append(dict(tier=tier, outcome=oc, outcome_label=label, unit=unit, db=db,
                         effect=r['effect'], lo=r['lo'], hi=r['hi'], p=r['p'],
                         n=r['n'], n_arth1=r['n_arth1'], n_cluster=r['n_cluster']))
        forest.append(dict(tier=tier, outcome=oc, db=db, effect=r['effect'],
                           lo=r['lo'], hi=r['hi'], n=r['n']))
    if m:
        rows.append(dict(tier=tier, outcome=oc, outcome_label=label, unit=unit,
                         db='POOLED (RE)', effect=m['pooled_effect'], lo=m['lo'], hi=m['hi'],
                         p=m['p'], n=np.nan, n_arth1=np.nan, n_cluster=m['k']))
        forest.append(dict(tier=tier, outcome=oc, db='POOLED (RE)',
                           effect=m['pooled_effect'], lo=m['lo'], hi=m['hi'], n=np.nan))
        log(f"{tier:<9s} {oc:<34s} {m['pooled_effect']:.3f} ({m['lo']:.3f}-{m['hi']:.3f}) "
            f"I2={m['I2']:.1f}% tau2={m['tau2']:.4f} Q_p={m['Q_p']:.3g} k={m['k']}")

T = pd.DataFrame(rows)
T.to_csv(os.path.join(OUT, '22_1a_main_table.csv'), index=False, encoding='utf-8-sig', float_format='%.4f')
T[T.tier=='secondary'].to_csv(os.path.join(OUT, '22_1a_secondary_table.csv'), index=False,
                              encoding='utf-8-sig', float_format='%.4f')
pd.DataFrame(forest).to_csv(os.path.join(OUT, '22_1a_forest.csv'), index=False,
                            encoding='utf-8-sig', float_format='%.4f')

# ---- 敏感性矩阵 ----
sens = []
for set_ in S['set'].unique():
    for oc in ['P1_any_oop','P2_amount_log','P2inc_amount_log_adj_income',
               'B10_oop_ge10pct_income','B40_oop_ge40pct_income','P2_gamma_glm',
               'CHE10_consumption_denominator']:
        m = meta_row(set_, oc)
        if m:
            sens.append(dict(set=set_, outcome=oc, pooled=m['pooled_effect'], lo=m['lo'],
                             hi=m['hi'], p=m['p'], I2=m['I2'], tau2=m['tau2'], k=m['k']))
SD = pd.DataFrame(sens)
SD.to_csv(os.path.join(OUT, '22_1a_sensitivity_table.csv'), index=False,
          encoding='utf-8-sig', float_format='%.4f')

# ---- g-comp 按库报告（不合并） ----
G.to_csv(os.path.join(OUT, '22_1a_gcomp.csv'), index=False, encoding='utf-8-sig', float_format='%.2f')

log("\n########## 敏感性（合并值） ##########")
for r in SD[SD.outcome.isin(['P1_any_oop','P2inc_amount_log_adj_income'])].itertuples():
    log(f"  {r.set:<18s} {r.outcome:<34s} {r.pooled:.3f} ({r.lo:.3f}-{r.hi:.3f}) I2={r.I2:.1f}% k={r.k}")

log("\n########## 归因自付（g-comp，2020 国际元/年，按库报告不合并） ##########")
for r in G.itertuples():
    log(f"  {r.db:<8s} E1={r.expected_oop_arth1_2020intl:>9,.1f}  "
        f"E0={r.expected_oop_arth0_2020intl:>9,.1f}  归因={r.attributable_oop_2020intl:>8,.1f}  "
        f"smear={r.smearing:.3f}")

log("\n########## 消费 CHE（可得子样本） ##########")
for r in S[(S['set']=='che_cons')].itertuples():
    log(f"  {r.db:<8s} OR={r.effect:.3f} ({r.lo:.3f}-{r.hi:.3f}) n={r.n:,}")
log("\n########## CHARLS 扩展库（不进主 meta） ##########")
for r in S[(S['set']=='charls_ext')].itertuples():
    log(f"  {r.outcome:<34s} {r.effect:.3f} ({r.lo:.3f}-{r.hi:.3f}) n={r.n:,}")

# ---- 供写作的数字清单与措辞红线 ----
md = []
md.append('# 1a 定稿：A1 可写入正文的数字清单（英文稿）\n')
md.append('> 本文件只列**可直接写进正文/摘要的数字**与措辞边界，不组装正文。'
          '所有数字来自 `20_*` / `21_*`，1a 版主表见 `22_1a_main_table.csv`。\n')
md.append('## 1. 主结局（两个，均为校正后关联）\n')
md.append('| Outcome | MHAS | HRS | SHARE | LASI | Pooled RE (95% CI) | I² |\n|---|---:|---:|---:|---:|---:|---:|')
for oc, unit, label in PRIMARY:
    m = meta_row('main_revised', oc)
    cells = []
    for db in MAIN:
        r = db_row('main_revised', db, oc)
        cells.append(f"{r['effect']:.3f}" if r else '—')
    md.append(f"| {label} ({unit}) | " + ' | '.join(cells) +
              f" | **{m['pooled_effect']:.3f} ({m['lo']:.3f}–{m['hi']:.3f})** | {m['I2']:.1f}% |")
md.append('\n协变量：年龄(每10岁)、性别、婚姻、教育、自评健康、ADL、糖尿病、高血压、卒中、'
          '城乡(HRS 无)、波次固定效应；SHARE 另加国家固定效应。加权、个体 ID 聚类稳健 SE。')
md.append('P2inc 额外控制 log(家庭收入)；对分母的常数缩放稳健。')
md.append('分析样本：四库 25 波、576,020 人波；P2inc 限有正支出且家庭收入 >0。\n')
md.append('## 2. 次要结局（必须带限制性说明）\n')
md.append('| Outcome | MHAS | HRS | SHARE† | LASI | Pooled RE (95% CI) | I² |\n|---|---:|---:|---:|---:|---:|---:|')
for oc, unit, label in SECOND[:2]:
    m = meta_row('main_revised', oc)
    cells = []
    for db in MAIN:
        r = db_row('main_revised', db, oc)
        cells.append(f"{r['effect']:.3f}" if r else '—')
    md.append(f"| {label} (OR) | " + ' | '.join(cells) +
              f" | {m['pooled_effect']:.3f} ({m['lo']:.3f}–{m['hi']:.3f}) | {m['I2']:.1f}% |")
md.append('\n† SHARE 阈值结局仅 w1（w2/w5/w6 收入变量与 w1 相差约 10.32 倍，属口径不同）。')
md.append('B40 合并值不显著且 HRS/SHARE 校正后方向反转，**不得作为主要结论**，'
          '统一写 "should be interpreted cautiously"。')
md.append('命名：一律 **income-based financial burden**，**不得**称 WHO-style CHE。\n')
md.append('## 3. 敏感性 / 扩展（不得并入主 meta）\n')
md.append('- 排除插补、1/99% 缩尾、未加权、最小调整：P1 与 P2inc 方向不变、幅度近似。')
md.append('- Gamma GLM(log link) 金额比逐库 1.048–1.105，低于 log-OLS 的 1.13–1.19；'
          '属条件均值 vs 条件几何均值差异，须在 Methods 并列报告。')
md.append('- 消费分母 CHE（可得子样本）：四库 OR 1.225–1.280、方向一致且显著，'
          '单列为 "consumption-based catastrophic expenditure in the subsample where data were available"。')
md.append('- CHARLS 扩展库 P1 显著、金额比不显著（自建总额漏药费 1–2%），不进主 meta。')
md.append('- SHARE 收入经验校正 /10.3178 仅作敏感性，未经官方 codebook 确认。\n')
md.append('## 4. 归因自付（2020 国际元/年，按库报告，不合并）\n')
md.append('| Cohort | E[OOP | arth=1] | E[OOP | arth=0] | Attributable |\n|---|---:|---:|---:|')
for r in G.itertuples():
    md.append(f"| {r.db.upper()} | {r.expected_oop_arth1_2020intl:,.1f} | "
              f"{r.expected_oop_arth0_2020intl:,.1f} | {r.attributable_oop_2020intl:,.1f} |")
md.append('\nlog-OLS 反变换 smearing 2.47–3.24，右尾较重；绝对量须结合 Gamma GLM 一并解读。\n')
md.append('## 5. 措辞红线\n')
md.append('- ✅ "to our knowledge, the first multi-cohort harmonised estimate"')
md.append('- ❌ "first study of arthritis out-of-pocket spending"（2003 AHEAD 已做）')
md.append('- ❌ "causal effect"；用 "was associated with" / "should be interpreted cautiously"')
md.append('- ❌ 不用 "modest" / "altered inference" / "correction"；'
          '口径处理写 "harmonisation / rescaling in sensitivity analysis"')
md.append('- ❌ 不做 naïve pooling；绝对金额只按库报告，仅相对效应做随机效应合并')
md.append('- I² >85% 必须报告异质性，不得只报合并值；k=4 时 τ² 估计不稳定，须注明')
md.append('- Table 1 组间差异一律标注 unadjusted')
md.append('- `arthre` = self-reported ever-diagnosed arthritis/rheumatism；'
          '**不可**写成 RA / OA / gout / osteoporosis 或 clinical diagnosis')
with open(os.path.join(OUT, '22_1a_manuscript_numbers.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(md) + '\n')

log(f"\nDONE: 主表 {len(T)} 行、森林图 {len(forest)} 行、敏感性 {len(SD)} 行")
log("输出：22_1a_main_table.csv / 22_1a_secondary_table.csv / 22_1a_sensitivity_table.csv /")
log("      22_1a_forest.csv / 22_1a_gcomp.csv / 22_1a_manuscript_numbers.md")
