# -*- coding: utf-8 -*-
"""方向 A / 任务 11 主模型：按库分别估计 -> 随机效应 meta（不做 naïve pooling）。
结局：
  P1 有无自付 logit（GLM binomial, 加权, 个体聚类稳健）
  P2 有支出者年化金额 log-OLS（WLS, 个体聚类稳健）；金额已 PPP+CPI 平减至 2020 国际元
  B10/B40 OOP/家庭收入 >=10%/>=40% logit（income-based financial burden，不称 WHO CHE）
  GCOMP 标准化 g-computation 得关节炎归因自付（2020 国际元/年），按库报告
  SHARE 另按国家分层估计，作为 A4 制度梯度的素材
输出：20_a1_main_results.csv / 20_a1_meta.csv / 20_a1_gcomp.csv /
      20_a1_share_by_country.csv / 20_table1.csv / 20_a1_main.txt / 20_forest_data.csv
用法：python 20_fit_a1_main.py [db ...]  # 不传参则跑四库主分析
"""
import os, sys, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '20_a1_main.txt')
MAIN = ['mhas','hrs','share','lasi']
DBS = [x for x in sys.argv[1:] if x in MAIN + ['charls']] or MAIN
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def design(d, db, minimal=False):
    """构造设计矩阵；自动剔除常数列（HRS 无 rural、LASI 单波等）。"""
    X = pd.DataFrame(index=d.index)
    X['arth'] = d['arth'].astype(float)
    X['age10'] = (d['age'] - 70.0) / 10.0
    X['female'] = d['female']
    X['married'] = d['married']
    X['shlt'] = d['shlt']
    X['adl_any'] = d['adl_any']
    if not minimal:
        X['diabe'] = d['diabe']; X['hibpe'] = d['hibpe']; X['stroke'] = d['stroke']
        if d['rural'].nunique() > 1: X['rural'] = d['rural']
    for c, pre in [('educ','edu'), ('wave','wv')]:
        dum = pd.get_dummies(d[c].astype('Int64').astype(str), prefix=pre, drop_first=True)
        X = pd.concat([X, dum], axis=1)
    if db == 'share' and not minimal and d['iso3'].nunique() > 1:
        X = pd.concat([X, pd.get_dummies(d['iso3'].astype(str), prefix='cty', drop_first=True)], axis=1)
    X = X.astype(float)
    keep = [c for c in X.columns if X[c].nunique(dropna=False) > 1]
    X = sm.add_constant(X[keep], has_constant='add')
    return X

def fit_glm(y, X, w, g):
    try:
        r = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w).fit(
            cov_type='cluster', cov_kwds={'groups': g}, maxiter=100)
        return r, 'cluster'
    except Exception as e:
        r = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w).fit(maxiter=100)
        return r, 'HC0_fallback:' + type(e).__name__

def fit_wls(y, X, w, g):
    try:
        r = sm.WLS(y, X, weights=w).fit(cov_type='cluster', cov_kwds={'groups': g})
        return r, 'cluster'
    except Exception as e:
        r = sm.WLS(y, X, weights=w).fit(cov_type='HC0')
        return r, 'HC0_fallback:' + type(e).__name__

def extract(res, cov, db, outcome, n, n1, nclus, extra=None):
    b = float(res.params['arth']); se = float(res.bse['arth'])
    p = 2*stats.norm.sf(abs(b/se))
    d = dict(db=db, outcome=outcome, beta=b, se=se,
             effect=float(np.exp(b)), lo=float(np.exp(b-1.96*se)),
             hi=float(np.exp(b+1.96*se)), p=p, n=int(n),
             n_arth1=int(n1), n_cluster=int(nclus), cov=cov)
    if extra: d.update(extra)
    return d

def meta_dl(rows):
    """DerSimonian-Laird 随机效应合并；输入 beta/se。k 小时 tau2 不稳定，报告中注明。"""
    y = np.array([r['beta'] for r in rows]); se = np.array([r['se'] for r in rows])
    k = len(y); w = 1/se**2
    mu_f = (w*y).sum()/w.sum()
    Q = float((w*(y-mu_f)**2).sum())
    C = w.sum() - (w**2).sum()/w.sum()
    tau2 = max(0.0, (Q-(k-1))/C) if C > 0 else 0.0
    wr = 1/(se**2+tau2)
    mu = float((wr*y).sum()/wr.sum()); semu = float(np.sqrt(1/wr.sum()))
    I2 = max(0.0, (Q-(k-1))/Q*100) if Q > 0 else 0.0
    return dict(k=k, pooled_beta=mu, pooled_se=semu,
                pooled_effect=float(np.exp(mu)),
                pooled_lo=float(np.exp(mu-1.96*semu)),
                pooled_hi=float(np.exp(mu+1.96*semu)),
                pooled_p=float(2*stats.norm.sf(abs(mu/semu))),
                Q=Q, Q_p=float(stats.chi2.sf(Q, k-1)) if k > 1 else None,
                I2=I2, tau2=tau2)

log("方向 A / 任务 11：A1 主模型｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("按库分别估计 -> DerSimonian-Laird 随机效应合并；不做 naïve pooling。")
log("结局：P1 有无自付 / P2 有支出者金额(log) / B10、B40 OOP/收入阈值 / GCOMP 归因金额。")
log("权重=各库个体权重按 库×国家 归一化；SE 按个体 ID 聚类稳健。\n")

DATA = {}
for db in ['mhas','hrs','share','lasi','charls']:
    p = os.path.join(OUT, f'18_data_{db}.csv')
    if os.path.exists(p):
        DATA[db] = pd.read_csv(p, low_memory=False)

res_rows, gcomp_rows, table1_rows, country_rows = [], [], [], []
for db in DBS:
    d = DATA[db].copy()
    d['pos'] = (d['oop_annual_lcu'] > 0).astype(float)
    d['logoop'] = np.where(d['oop_2020intl'] > 0, np.log(d['oop_2020intl']), np.nan)
    log(f"\n########## {db} ##########  n={len(d):,} 波次={sorted(d.wave.unique())}")
    # ---- Table 1（加权、按关节炎分组，标注 unadjusted） ----
    for lab, g in d.groupby('arth'):
        table1_rows.append(dict(db=db, group='arth=1' if lab==1 else 'arth=0',
            n=len(g), age=round(float(np.average(g.age, weights=g.weight)),1),
            female_pct=round(100*float(np.average(g.female, weights=g.weight)),1),
            any_oop_pct=round(100*float(np.average(g.pos, weights=g.weight)),1),
            median_oop_2020intl=round(float(g.oop_2020intl.median()),1),
            median_oop_positive_2020intl=round(float(g.loc[g.pos==1,'oop_2020intl'].median()),1),
            burden10_pct=round(100*float(np.nanmean(g.burden10)),1),
            burden40_pct=round(100*float(np.nanmean(g.burden40)),1),
            adl_any_pct=round(100*float(np.average(g.adl_any, weights=g.weight)),1)))
    X = design(d, db)
    w = d['weight'].clip(lower=0.01)
    g = d['id'].astype(str)
    nclus = g.nunique()
    # ---- P1 ----
    t0=time.time()
    r1, cov1 = fit_glm(d['pos'], X, w, g)
    res_rows.append(extract(r1, cov1, db, 'P1_any_oop', len(d), int((d.arth==1).sum()), nclus))
    log(f"  P1 有无自付: OR={np.exp(r1.params['arth']):.3f} "
        f"({np.exp(r1.params['arth']-1.96*r1.bse['arth']):.3f}-{np.exp(r1.params['arth']+1.96*r1.bse['arth']):.3f}) "
        f"p={2*stats.norm.sf(abs(r1.params['arth']/r1.bse['arth'])):.2e} [{cov1}] {time.time()-t0:.1f}s")
    # ---- P2 ----
    sub = d[d['logoop'].notna()].copy()
    X2 = design(sub, db); w2 = sub['weight'].clip(lower=0.01); g2 = sub['id'].astype(str)
    r2, cov2 = fit_wls(sub['logoop'], X2, w2, g2)
    res_rows.append(extract(r2, cov2, db, 'P2_amount_log', len(sub),
                            int((sub.arth==1).sum()), g2.nunique()))
    log(f"  P2 有支出者金额: 比值={np.exp(r2.params['arth']):.3f} "
        f"({np.exp(r2.params['arth']-1.96*r2.bse['arth']):.3f}-{np.exp(r2.params['arth']+1.96*r2.bse['arth']):.3f}) "
        f"n={len(sub):,} [{cov2}] {time.time()-t0:.1f}s")
    # ---- g-computation 归因自付 ----
    smear = float(np.mean(np.exp(r2.resid)))
    Xa = design(d, db).reindex(columns=X.columns, fill_value=0)  # 同列结构
    X1 = Xa.copy(); X1['arth'] = 1.0
    X0 = Xa.copy(); X0['arth'] = 0.0
    p1 = np.asarray(r1.predict(X1)); p0 = np.asarray(r1.predict(X0))
    m1 = np.exp(np.asarray(r2.predict(X1.reindex(columns=X2.columns, fill_value=0))))*smear
    m0 = np.exp(np.asarray(r2.predict(X0.reindex(columns=X2.columns, fill_value=0))))*smear
    e1 = float(np.average(p1*m1, weights=w)); e0 = float(np.average(p0*m0, weights=w))
    gcomp_rows.append(dict(db=db, expected_oop_arth1_2020intl=e1,
                           expected_oop_arth0_2020intl=e0,
                           attributable_oop_2020intl=e1-e0,
                           smearing=smear, n=len(d)))
    log(f"  GCOMP 归因自付 = {e1-e0:,.1f} 2020国际元/年 (E1={e1:,.1f} / E0={e0:,.1f}; smear={smear:.3f})")
    # ---- B10 / B40 ----
    for ycol, lab in [('burden10','B10_oop_ge10pct_income'),('burden40','B40_oop_ge40pct_income')]:
        s = d[d[ycol].notna()].copy()
        Xs = design(s, db); ws = s['weight'].clip(lower=0.01); gs = s['id'].astype(str)
        rb, covb = fit_glm(s[ycol], Xs, ws, gs)
        res_rows.append(extract(rb, covb, db, lab, len(s), int((s.arth==1).sum()), gs.nunique()))
        log(f"  {lab}: OR={np.exp(rb.params['arth']):.3f} "
            f"({np.exp(rb.params['arth']-1.96*rb.bse['arth']):.3f}-{np.exp(rb.params['arth']+1.96*rb.bse['arth']):.3f}) "
            f"n={len(s):,}")
    # ---- SHARE 按国家分层 ----
    if db == 'share':
        log("  --- SHARE 按国家分层（A4 素材）---")
        for iso, s in d.groupby('iso3'):
            if len(s) < 800 or s['pos'].nunique() < 2:
                continue
            try:
                Xc = design(s, 'share', minimal=False)
                Xc = Xc[[c for c in Xc.columns if not c.startswith('cty_')]]
                rc, _ = fit_glm(s['pos'], Xc, s['weight'].clip(lower=0.01), s['id'].astype(str))
                sc = s[s['logoop'].notna()]
                Xc2 = design(sc, 'share'); Xc2 = Xc2[[c for c in Xc2.columns if not c.startswith('cty_')]]
                rc2, _ = fit_wls(sc['logoop'], Xc2, sc['weight'].clip(lower=0.01), sc['id'].astype(str))
                country_rows.append(dict(iso3=iso, n=len(s), n_arth1=int((s.arth==1).sum()),
                    or_any_oop=float(np.exp(rc.params['arth'])), se_or=float(rc.bse['arth']),
                    ratio_amount=float(np.exp(rc2.params['arth'])), se_ratio=float(rc2.bse['arth']),
                    burden10_pct=round(100*float(np.nanmean(s.burden10)),1)))
            except Exception as e:
                log(f"    {iso}: 失败 {type(e).__name__} {str(e)[:80]}")
        log(f"    完成 {len(country_rows)} 个国家 -> 20_a1_share_by_country.csv")

# ---- 随机效应 meta ----
meta = []
for oc in ['P1_any_oop','P2_amount_log','B10_oop_ge10pct_income','B40_oop_ge40pct_income']:
    rows = [r for r in res_rows if r['outcome']==oc and r['db'] in MAIN]
    if len(rows) >= 2:
        m = meta_dl(rows); m['outcome'] = oc
        meta.append(m)
        log(f"\nMETA {oc}: 合并效应={m['pooled_effect']:.3f} "
            f"({m['pooled_lo']:.3f}-{m['pooled_hi']:.3f}) I2={m['I2']:.1f}% tau2={m['tau2']:.4f} "
            f"Q={m['Q']:.1f} p_het={m['Q_p']:.3g} k={m['k']}")

# ---- 落盘 ----
with open(os.path.join(OUT,'20_a1_main_results.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(res_rows).to_csv(f, index=False, float_format='%.6f')
with open(os.path.join(OUT,'20_a1_meta.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(meta).to_csv(f, index=False, float_format='%.6f')
with open(os.path.join(OUT,'20_a1_gcomp.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(gcomp_rows).to_csv(f, index=False, float_format='%.4f')
with open(os.path.join(OUT,'20_table1.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(table1_rows).to_csv(f, index=False)
if country_rows:
    with open(os.path.join(OUT,'20_a1_share_by_country.csv'),'w',encoding='utf-8-sig',newline='') as f:
        pd.DataFrame(country_rows).to_csv(f, index=False, float_format='%.4f')
# 森林图数据
fc = pd.DataFrame([dict(db=r['db'], outcome=r['outcome'], effect=r['effect'],
                        lo=r['lo'], hi=r['hi'], n=r['n']) for r in res_rows] +
                  [dict(db='POOLED (RE)', outcome=m['outcome'], effect=m['pooled_effect'],
                        lo=m['pooled_lo'], hi=m['pooled_hi'], n=None) for m in meta])
with open(os.path.join(OUT,'20_forest_data.csv'),'w',encoding='utf-8-sig',newline='') as f:
    fc.to_csv(f, index=False, float_format='%.4f')
log(f"\nDONE: {len(res_rows)} 个模型，{len(meta)} 个 meta 结局，{len(gcomp_rows)} 条 g-comp")
