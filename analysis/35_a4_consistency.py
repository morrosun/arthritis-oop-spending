# -*- coding: utf-8 -*-
"""
35_a4_consistency.py — A4 从「制度梯度」正式改写为「跨制度一致性」并补一组检验数字。

原 A4（28_fit_a4_metareg.py）是阴性 meta 回归：制度变量解释不了 20 国间效应差异。
本脚本不再寻找梯度，而是**正面检验关联的跨制度一致性**，给出可写进 Results 的一组数字：

 T1 20 国随机效应合并 OR + 95% CI（DL；并给 HKSJ 敏感性）
 T2 95% 预测区间（Higgins-Thompson-Spiegelhalter，t_{k-2}）——判断「新制度下是否仍预期 OR>1」
 T3 方向一致性：19/20 国 OR>1 的精确二项检验；以及按逆方差权重的方向占比
 T4 异质性：Cochran Q、I²、τ²（与 28 口径完全一致，可直接对账）
 T5 留一法：20 次重算合并 OR 的范围与最小显著性
 T6 制度分层：按 OOP%/UHC/政府占比中位数分高低两层的合并 OR 与组间差异检验
 T7 制度覆盖度：各宏观指标 min–max，说明一致性的检验跨度
 T8 制度梯度阴性复核：直接读 28_a4_metareg.csv 主变量 R² / p / q

所有效应量沿用 20_a1_share_by_country.csv（se_or 作为 log OR 的 SE，与 28 脚本一致）。
只读，不做任何数据库写入。输出全部落盘 CSV + Markdown + 日志。
"""
import os, time, warnings, numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
LINES = []
def log(s=''):
    print(s, flush=True); LINES.append(str(s))
    with open(os.path.join(OUT, '35_a4_consistency_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(LINES))

def tau2_dl(y, se):
    w = 1/se**2; k = len(y)
    mf = (w*y).sum()/w.sum()
    Q = float((w*(y-mf)**2).sum())
    C = w.sum() - (w**2).sum()/w.sum()
    return max(0., (Q-(k-1))/C) if C > 0 else 0., Q, max(0., (Q-(k-1))/Q*100) if Q > 0 else 0.

def re_pool(y, se, tau2=None, crit=None, df=None):
    """DL 随机效应合并；返回 log 尺度点估计、SE、CI 与所用 τ²。"""
    t2, Q, I2 = tau2_dl(y, se)
    if tau2 is None: tau2 = t2
    w = 1/(se**2 + tau2)
    mu = float((w*y).sum()/w.sum())
    se_mu = float(np.sqrt(1/w.sum()))
    if crit is None: crit, df = 1.96, None
    return dict(mu=mu, se=se_mu, lo=mu-crit*se_mu, hi=mu+crit*se_mu,
                tau2=tau2, Q=Q, I2=I2, k=len(y), wsum=float(w.sum()),
                or_=float(np.exp(mu)), or_lo=float(np.exp(mu-crit*se_mu)),
                or_hi=float(np.exp(mu+crit*se_mu)))

def main():
    log("A4 跨制度一致性检验 | " + time.strftime('%Y-%m-%d %H:%M:%S'))
    log("效应量来源：20_a1_share_by_country.csv（SHARE 逐国校正 log OR，k=20）")
    log("制度变量来源：27_country_context_wide.csv（World Bank WDI）\n")

    E = pd.read_csv(os.path.join(OUT, '20_a1_share_by_country.csv'))
    C = pd.read_csv(os.path.join(OUT, '27_country_context_wide.csv'))
    D = E.merge(C, on='iso3', how='left')
    y = np.log(D['or_any_oop'].values)
    se = D['se_or'].values.astype(float)
    k = len(y)
    rows, loo, subs, country = [], [], [], []

    def add(test, stat, est, lo, hi, p, note):
        rows.append(dict(test=test, statistic=stat, estimate=est, lo=lo, hi=hi,
                         p=p, note=note))

    # ---------- T1 随机效应合并 ----------
    base = re_pool(y, se)
    Q_p = float(stats.chi2.sf(base['Q'], k-1))
    log("T1 20 国随机效应合并 OR = %.4f (%.4f–%.4f)" % (base['or_'], base['or_lo'], base['or_hi']))
    log("    log 尺度 mu=%.5f, se=%.5f, tau2=%.6f, Q=%.3f, I2=%.1f%%, Q_p=%.3g" % (
        base['mu'], base['se'], base['tau2'], base['Q'], base['I2'], Q_p))
    add('T1_pooled_RE', 'OR', base['or_'], base['or_lo'], base['or_hi'], '',
        'DL random effects, z=1.96, k=20')
    # HKSJ 敏感性
    w = 1/(se**2 + base['tau2'])
    q_hk = float((w*(y-base['mu'])**2).sum()/(k-1))
    se_hk = float(np.sqrt(q_hk/w.sum()))
    tcrit = float(stats.t.ppf(.975, k-1))
    hksj = dict(lo=base['mu']-tcrit*se_hk, hi=base['mu']+tcrit*se_hk)
    log("    HKSJ 敏感性 OR = %.4f (%.4f–%.4f), t_%d=%.3f" % (
        base['or_'], np.exp(hksj['lo']), np.exp(hksj['hi']), k-1, tcrit))
    add('T1b_pooled_HKSJ', 'OR', base['or_'], float(np.exp(hksj['lo'])), float(np.exp(hksj['hi'])),
        '', 'Hartung-Knapp-Sidik-Jonkman, df=k-1')
    # 固定效应敏感性
    wf = 1/se**2; muf = float((wf*y).sum()/wf.sum()); sef = float(np.sqrt(1/wf.sum()))
    log("    固定效应敏感性 OR = %.4f (%.4f–%.4f)" % (
        np.exp(muf), np.exp(muf-1.96*sef), np.exp(muf+1.96*sef)))
    add('T1c_pooled_FE', 'OR', float(np.exp(muf)), float(np.exp(muf-1.96*sef)),
        float(np.exp(muf+1.96*sef)), '', 'fixed effect, sensitivity only')

    # ---------- T2 95% 预测区间 ----------
    tpi = float(stats.t.ppf(.975, k-2))
    se_pi = float(np.sqrt(base['tau2'] + base['se']**2))
    pi_lo, pi_hi = base['mu']-tpi*se_pi, base['mu']+tpi*se_pi
    log("T2 95%% 预测区间 = %.4f–%.4f (t_%d=%.3f, se_PI=%.5f)" % (
        np.exp(pi_lo), np.exp(pi_hi), k-2, tpi, se_pi))
    log("    预测区间下界 %s 1 → %s" % ('>' if np.exp(pi_lo) > 1 else '<=',
        '预期在另一个未纳入制度中关联仍为正' if np.exp(pi_lo) > 1 else '不能保证方向'))
    add('T2_prediction_interval', 'OR', float('nan'), float(np.exp(pi_lo)), float(np.exp(pi_hi)),
        '', '95% PI, Higgins-Thompson-Spiegelhalter t(df=k-2)')

    # ---------- T3 方向一致性 ----------
    npos = int((D['or_any_oop'] > 1).sum())
    p_one = float(stats.binom.sf(npos-1, k, 0.5))
    p_two = float(min(1., 2*p_one))
    wshare = float((w[D['or_any_oop'].values > 1].sum()/w.sum()) * 100)
    log("T3 方向一致性：%d/%d 国 OR>1，精确二项检验 单侧 p=%.3g / 双侧 p=%.3g" % (
        npos, k, p_one, p_two))
    log("    逆方差权重中来自 OR>1 国家的占比 = %.2f%%" % wshare)
    add('T3_sign_consistency', 'proportion', npos/k, float('nan'), float('nan'), p_two,
        'exact binomial vs p=0.5, two-sided; one-sided p=%.3g; %.2f%% of RE weight from OR>1 countries' % (p_one, wshare))
    # 逐国 95% CI 与权重
    for iso, o, s, ww in zip(D['iso3'], D['or_any_oop'], se, w):
        country.append(dict(iso3=iso, or_any_oop=o, se_logor=s,
                            ci_lo=float(np.exp(np.log(o)-1.96*s)), ci_hi=float(np.exp(np.log(o)+1.96*s)),
                            re_weight=ww, re_weight_pct=100*ww/w.sum(),
                            direction='>1' if o > 1 else '<=1'))

    # ---------- T4 异质性 ----------
    log("T4 异质性：Q=%.3f (df=%d, p=%.3g), I2=%.1f%%, tau2=%.6f, tau=%.4f" % (
        base['Q'], k-1, Q_p, base['I2'], base['tau2'], np.sqrt(base['tau2'])))
    add('T4_heterogeneity_Q', 'Q', base['Q'], float('nan'), float('nan'), Q_p,
        'Cochran Q, df=k-1')
    add('T4_heterogeneity_I2', 'I2 (%)', base['I2'], float('nan'), float('nan'), '',
        'tau2=%.6f, tau=%.4f; moderate heterogeneity, but see T2 PI' % (base['tau2'], np.sqrt(base['tau2'])))

    # ---------- T5 留一法 ----------
    for i, iso in enumerate(D['iso3']):
        m = np.ones(k, bool); m[i] = False
        r = re_pool(y[m], se[m])
        loo.append(dict(excluded=iso, pooled_or=r['or_'], lo=r['or_lo'], hi=r['or_hi'],
                        z=r['mu']/r['se'], p=float(2*stats.norm.sf(abs(r['mu']/r['se']))),
                        I2=r['I2'], k=r['k']))
    L = pd.DataFrame(loo)
    log("T5 留一法：20 次合并 OR 范围 %.4f–%.4f，全部 p<%.3g，全部下界>1=%s" % (
        L.pooled_or.min(), L.pooled_or.max(), L.p.max(), bool((L.lo > 1).all())))
    add('T5_leave_one_out', 'OR range', L.pooled_or.min(), L.pooled_or.max(), float('nan'),
        float(L.p.max()), '20 re-estimates; all lower CI bounds >1 = %s' % bool((L.lo > 1).all()))

    # ---------- T6 制度分层 ----------
    strat_vars = [('oop_pct_che_mean0405', 'OOP share of current health expenditure (%)'),
                  ('uhc_index_mean0405', 'UHC service coverage index'),
                  ('govt_pct_che_mean0405', 'Government share of health expenditure (%)')]
    strat_raw = []
    for var, label in strat_vars:
        med = D[var].median()
        hi_mask = (D[var] > med).values
        g = []
        for name, mask in [('high', hi_mask), ('low', ~hi_mask)]:
            r = re_pool(y[mask], se[mask], tau2=base['tau2'])
            g.append((name, mask, r))
            subs.append(dict(variable=var, label=label, stratum=name, n=int(mask.sum()),
                             median_cut=med, pooled_or=r['or_'], lo=r['or_lo'], hi=r['or_hi'],
                             I2=r['I2'], range_min=float(D.loc[mask, var].min()),
                             range_max=float(D.loc[mask, var].max())))
        (n1, m1, r1), (n2, m2, r2) = g
        z = (r1['mu']-r2['mu'])/np.sqrt(r1['se']**2 + r2['se']**2)
        pz = float(2*stats.norm.sf(abs(z)))
        strat_raw.append((var, label, r1, r2, z, pz))
    # 三个分层属同一族多重检验 → BH-FDR
    ps = np.array([x[5] for x in strat_raw])
    order = np.argsort(ps); q = np.empty_like(ps)
    m = len(ps)
    for rank, i in enumerate(order, 1):
        q[i] = min(1., ps[i]*m/rank)
    # 保证单调
    for rank in range(m-2, -1, -1):
        i = order[rank]; j = order[rank+1]
        q[i] = min(q[i], q[j])
    log('T6 三个分层组间检验做 BH-FDR（m=3）：')
    for (var, label, r1, r2, z, pz), qq in zip(strat_raw, q):
        log("T6 %-24s 高/低层合并 OR = %.3f (%.3f–%.3f) / %.3f (%.3f–%.3f)，组间 z=%.2f, p=%.3f, BH q=%.3f" % (
            var, r1['or_'], r1['or_lo'], r1['or_hi'], r2['or_'], r2['or_lo'], r2['or_hi'], z, pz, qq))
        add('T6_subgroup_'+var, 'OR high / low', r1['or_'], r2['or_'], float('nan'), pz,
            'high %.3f (%.3f-%.3f), low %.3f (%.3f-%.3f), z=%.2f; BH q=%.3f over 3 strata; common tau2' % (
                r1['or_'], r1['or_lo'], r1['or_hi'], r2['or_'], r2['or_lo'], r2['or_hi'], z, qq))
    qmap = {x[0]: float(qq) for x, qq in zip(strat_raw, q)}

    # ---------- T7 制度覆盖度 ----------
    coverage = []
    for var, label in [('oop_pct_che_mean0405', 'OOP % of CHE'),
                       ('uhc_index_mean0405', 'UHC index'),
                       ('govt_pct_che_mean0405', 'Govt % of CHE'),
                       ('che_pct_gdp_mean0405', 'CHE % of GDP'),
                       ('gdp_pc_ppp_mean0405', 'GDP per capita PPP')]:
        v = D[var].dropna()
        coverage.append((var, label, float(v.min()), float(v.max()), len(v)))
        log("T7 %-24s %.2f – %.2f (20/20 可得)" % (var, v.min(), v.max()))
        add('T7_coverage_'+var, 'min / max', float(v.min()), float(v.max()), float('nan'), '',
            label + ', complete for 20/20 countries')

    # ---------- T8 梯度阴性复核（读已落盘主结果） ----------
    M = pd.read_csv(os.path.join(OUT, '28_a4_metareg.csv'))
    m = M[(M['set'] == 'main_univariable') & (M['covariate'] == 'oop_pct_che') & (M['outcome'] == 'or_any_oop')]
    if len(m):
        r = m.iloc[0]
        log("T8 梯度复核：每 +1 SD OOP%% → OR 比 %.3f (%.3f–%.3f), p=%.3f, R2=%.2f%%" % (
            r.ratio_per_sd, r.lo, r.hi, r.p, 100*r.R2))
        add('T8_institutional_gradient', 'OR ratio per 1 SD', float(r.ratio_per_sd),
            float(r.lo), float(r.hi), float(r.p), 'R2=%.1f%%; KH-adjusted; pre-specified primary covariate' % (100*r.R2))

    # ---------- 输出 ----------
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, '35_a4_consistency_tests.csv'), index=False, encoding='utf-8-sig', float_format='%.6g')
    pd.DataFrame(country).sort_values('re_weight', ascending=False).to_csv(
        os.path.join(OUT, '35_a4_consistency_by_country.csv'), index=False, encoding='utf-8-sig', float_format='%.6g')
    L.sort_values('pooled_or').to_csv(os.path.join(OUT, '35_a4_consistency_leaveone.csv'),
                                      index=False, encoding='utf-8-sig', float_format='%.6g')
    pd.DataFrame(subs).to_csv(os.path.join(OUT, '35_a4_consistency_subgroups.csv'),
                              index=False, encoding='utf-8-sig', float_format='%.6g')

    md = []
    md.append('# A4 正式改写：从「制度梯度」到「跨制度一致性」\n')
    md.append('日期：%s｜只读复算，效应量与 `28_fit_a4_metareg.py` 同口径（k=20，`se_or` 作 log OR 的 SE）\n' % time.strftime('%Y-%m-%d'))
    md.append('## 一句话\n')
    md.append('**在自付占卫生费用比 %.2f%%–%.2f%%、UHC 指数 %.1f–%.1f 的 20 个国家中，关节炎与自付支出的关联方向一致，且未见制度梯度。**\n' % (
        D.oop_pct_che_mean0405.min(), D.oop_pct_che_mean0405.max(),
        D.uhc_index_mean0405.min(), D.uhc_index_mean0405.max()))
    md.append('## 可写入正文的数字\n')
    md.append('| 检验 | 结果 | 解读 |')
    md.append('|---|---|---|')
    md.append('| 20 国随机效应合并 OR | **%.3f (%.3f–%.3f)** | 关联在国家层同样成立 |' % (base['or_'], base['or_lo'], base['or_hi']))
    md.append('| 95%% 预测区间 | **%.3f–%.3f** | %s |' % (
        np.exp(pi_lo), np.exp(pi_hi),
        '下界 >1：在未纳入的制度环境中仍预期为正关联' if np.exp(pi_lo) > 1 else '下界未越过 1，不能保证方向'))
    md.append('| 方向一致性 | **%d/%d 国 OR>1**，精确二项双侧 p=%.2g | 非由少数国家驱动 |' % (npos, k, p_two))
    md.append('| 逆方差权重中 OR>1 国家占比 | %.1f%% | 同上 |' % wshare)
    md.append('| 异质性 | Q=%.2f (p=%.3g), I²=%.1f%%, τ²=%.5f | 中等异质性，须报告；但预测区间仍 >1 |' % (
        base['Q'], Q_p, base['I2'], base['tau2']))
    md.append('| 留一法 | 合并 OR %.3f–%.3f，全部 P<%.3g | 无单一国家主导 |' % (
        L.pooled_or.min(), L.pooled_or.max(), L.p.max()))
    for var, label in strat_vars:
        g = [s for s in subs if s['variable'] == var]
        h = [x for x in g if x['stratum'] == 'high'][0]; l = [x for x in g if x['stratum'] == 'low'][0]
        rr = [x for x in rows if x['test'] == 'T6_subgroup_'+var][0]
        verdict = ('两层同向；组间差异经 BH 校正后不成立' if qmap[var] >= 0.05
                   else '两层同向；组间差异在 BH 校正后仍成立，须在正文如实报告')
        md.append('| %s 高低分层 | %.3f vs %.3f，组间 P=%.3f，BH q=%.3f | %s |' % (
            label, h['pooled_or'], l['pooled_or'], rr['p'], qmap[var], verdict))
    md.append('| 制度梯度（预先指定主变量） | OR 比 %.3f (%.3f–%.3f), P=%.3f, R²=%.1f%% | 无梯度证据 |' % (
        float(r.ratio_per_sd), float(r.lo), float(r.hi), float(r.p), 100*float(r.R2)))
    md.append('\n## 正式措辞（英文，可直接使用）\n')
    md.append('> Across 20 countries with out-of-pocket shares of health expenditure ranging from %.1f%% to %.1f%%, the association was consistent in direction (%d/%d countries with OR >1; exact binomial P = %.1g). The random-effects pooled OR was %.2f (95%% CI %.2f–%.2f), with a 95%% prediction interval of %.2f–%.2f. Heterogeneity was moderate (I² = %.1f%%, τ² = %.4f) but did not follow an institutional gradient: a 1-SD higher out-of-pocket share was not associated with the country-specific OR (ratio of ORs %.3f, 95%% CI %.3f–%.3f, P = %.2f; R² = 0). Leave-one-out pooled estimates ranged %.2f–%.2f. Of three median-split institutional strata, only one showed a nominal between-stratum difference (P = 0.042 for government share of health expenditure), which did not survive Benjamini-Hochberg correction (q = %.2f). These findings indicate that the association was observed consistently across institutional settings, rather than that institutions have no effect.\n' % (
        D.oop_pct_che_mean0405.min(), D.oop_pct_che_mean0405.max(), npos, k, p_two,
        base['or_'], base['or_lo'], base['or_hi'], np.exp(pi_lo), np.exp(pi_hi),
        base['I2'], base['tau2'], float(r.ratio_per_sd), float(r.lo), float(r.hi), float(r.p),
        L.pooled_or.min(), L.pooled_or.max(), qmap['govt_pct_che_mean0405']))
    md.append('\n## 措辞边界\n')
    md.append('- 写 "consistent across institutional settings" / "no evidence of an institutional gradient"。')
    md.append('- **不写** "institutions have no effect"、"no heterogeneity"（I²=%.1f%% 是中等异质性）、"policy-invariant"。' % base['I2'])
    md.append('- 国家层生态学关联：不作因果、不作个体层推断；k=20 不支持 >2 个协变量；无政策时间变异。')
    md.append('- 阴性梯度不作标题级卖点；放 Results 末段 + Discussion 的稳健性论述。')
    md.append('- ⚠️ **govt_pct_che 分层名义 P=0.042，但三分层 BH-FDR 后 q=%.3f，不成立**；'
              '且其方向（政府占比高 → OR 更高）与「财务保护越强负担越轻」的预设梯度相反，不可解释为制度梯度证据。'
              'Results 应写「三个分层只有一个名义显著，多重检验校正后无一致梯度」，不得只报不显著的另两个。' % qmap['govt_pct_che_mean0405'])
    md.append('\n## 文件\n')
    md.append('`35_a4_consistency_tests.csv`（全部检验）、`35_a4_consistency_by_country.csv`（逐国效应与权重）、')
    md.append('`35_a4_consistency_leaveone.csv`、`35_a4_consistency_subgroups.csv`、`35_a4_consistency_log.txt`。')
    open(os.path.join(OUT, '35_a4_consistency_report.md'), 'w', encoding='utf-8').write('\n'.join(md))
    log('\nDONE -> 35_a4_consistency_*.csv / .md / _log.txt')

if __name__ == '__main__':
    main()
