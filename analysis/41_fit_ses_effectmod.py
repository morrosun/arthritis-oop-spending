# -*- coding: utf-8 -*-
"""
41_fit_ses_effectmod.py — SES 分层效应修饰（为 International Journal for Equity in Health 补跑）

背景：IJEqH 关注「人群间系统性差异」。此前稿件只有「关节炎 vs 非关节炎」的组间差异，
      未回答该关联是否随社会经济地位（SES）变化。本脚本补一组预先设定的效应修饰分析，
      并额外给出「同样的相对超额在低收入家庭对应多大收入占比」的描述性翻译。

设计（全部与主分析 1a 口径一致）：
  结局（仅 1a 锁定的两个主结局；阈值结局 B10/B40 不进入 SES 分析，理由见报告）：
    P1   any OOP spending                加权 GLM-binomial，OR
    P2inc log(年化 OOP 2020 Int$) among spenders，控制 log 家庭收入，加权 WLS，金额比
  SES 轴（均为库内相对位置，不跨国比较绝对水平）：
    income_quintile  库×波内家庭收入秩五分位 Q1(最低)…Q5(最高)，仅 hhinc>0
    education        各库 educ 原码按教育层级近似归并为 low/middle/high（映射表见 EDU3）
  分析：
    (A) 分层估计：每个 (结局 × SES 轴 × 层) 在层内重估完整协变量模型，逐库；
        再对每层跨 4 库做 DerSimonian-Laird 随机效应合并。
    (B) 正式效应修饰检验：完整模型加入 SES 有序主效应 + arth×SES 交互项，逐库估计交互
        系数；exp(beta_int) = 每升高一个 SES 等级的 OR 比 / 金额比比（ratio of effects）。
        4 库交互系数做 DL 合并；2 结局 × 2 SES 轴 = 4 个检验，Benjamini-Hochberg FDR。
    (C) 描述性公平性翻译：按收入五分位给出关节炎组与对照组的加权平均年 OOP（2020 Int$）
        之差，以及该差占该层家庭收入中位数（2020 Int$）的百分比；报 Q1、Q5 与 Q1/Q5 比。
        纯未校正描述，不是标准化/因果归因；SHARE 仅用 w1（收入口径跨波不可比，诊断③）。

协变量：与 21/22 主分析完全相同的 design()（年龄/性别/婚姻/教育/波次/自评健康/ADL/
        糖尿病/高血压/卒中/可得时城乡；SHARE 另加国家固定效应），个体 ID 聚类稳健 SE，
        个体横断面权重。不跨库朴素合并个体记录。

措辞边界：效应修饰是关联性描述，不是因果；收入五分位是库内相对位置，不是绝对贫困线；
          不写「证明不公平 / 更不公平 / 政策失败」；不把 B10/B40 拉回主结论。

输出（全部增量落盘，前台运行）：
  41_ses_strata.csv        逐库 × 结局 × 轴 × 层 的分层估计
  41_ses_pooled.csv        每个 (结局 × 轴 × 层) 的跨库 DL 合并
  41_ses_interaction.csv   逐库 + 合并的交互检验（含 BH q）
  41_ses_tests.csv         正式检验汇总 T1–T8
  41_ses_equity.csv        描述性超额占收入比（逐库 × 收入五分位）
  41_ses_figure.csv        Figure 5 绘图数据（分层合并 OR/CI）
  41_ses_effectmod.log     运行日志
"""
import os, time, io, sys, warnings
import numpy as np
import pandas as pd
from scipy import stats
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
# 复用 21 主分析已验证的 design()/fit()/row()/meta_dl()，保证口径完全一致
_src = open(os.path.join(OUT, '21_fit_a1_revised.py'), encoding='utf-8').read()
exec(compile(_src.split('log("方向 A / 任务 11b')[0], '21_fit_a1_revised.py', 'exec'), globals())

MAIN = ['mhas', 'hrs', 'share', 'lasi']
LOGF = os.path.join(OUT, '41_ses_effectmod.log')
_lines = []
def log(s=''):
    print(s, flush=True)
    _lines.append(str(s))
    open(LOGF, 'w', encoding='utf-8').write('\n'.join(_lines))

# 各库 educ 原码 → 三层级近似归并（方向已验证：数值越大教育/收入越高，Spearman rho 0.23–0.47）
EDU3 = {
    'mhas':  {1: 'low', 2: 'middle', 3: 'high'},
    'hrs':   {1: 'low', 2: 'low',    3: 'middle', 4: 'high', 5: 'high'},
    'share': {1: 'low', 2: 'middle', 3: 'high'},
    'lasi':  {0: 'low', 1: 'low',    2: 'low', 3: 'middle', 4: 'middle',
              5: 'middle', 6: 'high', 7: 'high', 8: 'high', 9: 'high'},
}
EDU_SCORE = {'low': 0, 'middle': 1, 'high': 2}
AXES = {
    'income_quintile': dict(col='inc_q5', score='inc_score',
                            levels=[1, 2, 3, 4, 5], labels=['Q1 (lowest)', 'Q2', 'Q3', 'Q4', 'Q5 (highest)']),
    'education':       dict(col='edu3', score='edu_score',
                            levels=['low', 'middle', 'high'], labels=['Low', 'Middle', 'High']),
}
OUTCOMES = {
    'P1_any_oop':                    dict(y='pos',    kind='glm', loginc=False, lab='Any OOP (OR)'),
    'P2inc_amount_log_adj_income':   dict(y='logoop', kind='wls', loginc=True,  lab='Amount among spenders (ratio)'),
}

def prepare(db):
    d = pd.read_csv(os.path.join(OUT, f'18_data_{db}.csv'), low_memory=False).copy()
    inc = d['hhinc'].astype(float)
    d['inc_q5'] = np.nan
    ok = inc > 0
    d.loc[ok, 'inc_q5'] = np.ceil(d.loc[ok].groupby('wave')['hhinc'].rank(pct=True) * 5).clip(1, 5)
    d['inc_score'] = d['inc_q5'] - 1.0                       # 0=最低 … 4=最高
    d['edu3'] = d['educ'].map(EDU3[db])
    d['edu_score'] = d['edu3'].map(EDU_SCORE)
    d['pos'] = (d['oop_annual_lcu'] > 0).astype(float)
    amt = d['oop_2020intl'].astype(float)
    d['logoop'] = np.where(amt > 0, np.log(amt.clip(lower=1e-9)), np.nan)
    return d

DATA = {db: prepare(db) for db in MAIN}

def one_fit(s, db, oc, *, extra=None, param='arth', drop_prefix=()):
    """在子集 s 上拟合完整协变量模型；extra 为要追加的列 {name: array}。

    drop_prefix：交互模型里 SES 有序分数与某些原协变量是确定性函数关系
      （education 的 edu_score 由 educ 原码映射而来，与 edu_* 哑变量完全共线），
      必须从设计矩阵剔除，否则出现奇异矩阵、交互项标准误不可信。
    """
    cfg = OUTCOMES[oc]
    X = design(s, db, minimal=False, loginc=cfg['loginc'])
    if drop_prefix:
        drop = [c for c in X.columns
                if any(c.startswith(p) for p in drop_prefix)]
        X = X.drop(columns=drop)
    if extra:
        for k, v in extra.items():
            X[k] = np.asarray(v, dtype=float)
    w = s['weight'].clip(lower=0.01)
    g = s['id'].astype(str)
    r, cov = fit(s[cfg['y']], X, w, g, cfg['kind'])
    b = float(r.params[param]); se = float(r.bse[param])
    return dict(beta=b, se=se, effect=float(np.exp(b)),
                lo=float(np.exp(b - 1.96 * se)), hi=float(np.exp(b + 1.96 * se)),
                p=float(2 * stats.norm.sf(abs(b / se))) if se > 0 else np.nan,
                n=int(len(s)), n_arth1=int((s.arth == 1).sum()),
                n_cluster=int(g.nunique()), cov=cov)

# ---------------------------------------------------------------- (A) 分层估计
STRATA, POOLED = [], []
log('41 | SES 分层效应修饰 | ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('结局：P1(any OOP, OR) / P2inc(有支出者金额比, 控制 log 收入)；'
    'SES：收入五分位(库×波内) + 教育三层级(库内原码归并)')
log('完整协变量 + 个体 ID 聚类稳健 SE + 抽样权重；4 库分别估计，DL 随机效应合并。\n')

for oc in OUTCOMES:
    for ax, A in AXES.items():
        for lev, lab in zip(A['levels'], A['labels']):
            rows = []
            for db in MAIN:
                d = DATA[db]
                s = d[(d[A['col']] == lev) & d[OUTCOMES[oc]['y']].notna()]
                if len(s) < 300 or s[OUTCOMES[oc]['y']].nunique() < 2:
                    log(f'  SKIP {oc} {ax}={lab} {db}: n={len(s)}')
                    continue
                try:
                    r = one_fit(s, db, oc)
                except Exception as e:
                    log(f'  FAIL {oc} {ax}={lab} {db}: {type(e).__name__} {e}')
                    continue
                r.update(outcome=oc, axis=ax, stratum=str(lab), db=db)
                STRATA.append(r); rows.append(r)
                log(f'  {oc:32s} {ax:16s} {str(lab):14s} {db:6s} n={r["n"]:>7,} '
                    f'OR/比={r["effect"]:.3f} ({r["lo"]:.3f}–{r["hi"]:.3f})')
            if len(rows) >= 2:
                m = meta_dl(rows)
                m.update(outcome=oc, axis=ax, stratum=str(lab), k_meta=len(rows))
                POOLED.append(m)
                log(f'    -> pooled {oc} {ax}={lab}: {m["pooled_effect"]:.3f} '
                    f'({m["lo"]:.3f}–{m["hi"]:.3f}) I²={m["I2"]:.1f}% k={len(rows)}')
            # 增量落盘
            pd.DataFrame(STRATA).to_csv(os.path.join(OUT, '41_ses_strata.csv'),
                                        index=False, encoding='utf-8-sig', float_format='%.6f')
            pd.DataFrame(POOLED).to_csv(os.path.join(OUT, '41_ses_pooled.csv'),
                                        index=False, encoding='utf-8-sig', float_format='%.6f')

# ---------------------------------------------------------------- (B) 交互检验
INTER = []
log('\n########## (B) 正式效应修饰检验：arth × SES 有序交互 ##########')
for oc in OUTCOMES:
    for ax, A in AXES.items():
        rows = []
        for db in MAIN:
            d = DATA[db]
            s = d[d[OUTCOMES[oc]['y']].notna() & d[A['score']].notna()].copy()
            sc = s[A['score']].astype(float).values
            ar = s['arth'].astype(float).values
            # education 轴：edu_score 与 design() 的 edu_* 哑变量完全共线，剔除之
            dp = ('edu_',) if ax == 'education' else ()
            try:
                r = one_fit(s, db, oc,
                            extra={'ses_score': sc, 'arth_x_ses': ar * sc},
                            param='arth_x_ses', drop_prefix=dp)
            except Exception as e:
                log(f'  FAIL interaction {oc} {ax} {db}: {type(e).__name__} {e}')
                continue
            r.update(outcome=oc, axis=ax, db=db, n_total=int(len(s)))
            INTER.append(r); rows.append(r)
            log(f'  {oc:32s} {ax:16s} {db:6s} n={r["n"]:>7,} '
                f'ratio-of-effects/级={r["effect"]:.4f} ({r["lo"]:.4f}–{r["hi"]:.4f}) P={r["p"]:.4f}')
        if len(rows) >= 2:
            m = meta_dl(rows)
            m.update(outcome=oc, axis=ax, db='POOLED (RE)', k_meta=len(rows))
            # meta_dl 只给 pooled_effect；逐库行用 effect。交付 CSV 两列并存，
            # 避免 pooled 行 effect 留空导致下游按 effect 取数时静默出错。
            m['effect'] = m['pooled_effect']
            INTER.append(m)
            log(f'    -> pooled interaction {oc} {ax}: {m["pooled_effect"]:.4f} '
                f'({m["lo"]:.4f}–{m["hi"]:.4f}) P={m["p"]:.4f} I²={m["I2"]:.1f}%')
        pd.DataFrame(INTER).to_csv(os.path.join(OUT, '41_ses_interaction.csv'),
                                   index=False, encoding='utf-8-sig', float_format='%.6f')

# BH-FDR：4 个合并交互检验
pool_int = [r for r in INTER if r.get('db') == 'POOLED (RE)']
ps = np.array([r['p'] for r in pool_int])
order = np.argsort(ps); q = np.empty_like(ps); m = len(ps)
prev = 1.0
for rank, i in enumerate(order[::-1], 1):
    val = min(prev, ps[i] * m / (m - rank + 1))
    q[i] = val; prev = val
for r, qq in zip(pool_int, q):
    r['bh_q'] = float(qq)
pd.DataFrame(INTER).to_csv(os.path.join(OUT, '41_ses_interaction.csv'),
                           index=False, encoding='utf-8-sig', float_format='%.6f')
log('\n  BH-FDR (4 检验): ' + ' | '.join(
    f'{r["outcome"].split("_")[0]}×{"inc" if r["axis"]=="income_quintile" else "edu"} '
    f'P={r["p"]:.4f} q={r["bh_q"]:.4f}' for r in pool_int))

# ---------------------------------------------------------------- (C) 描述性公平性翻译
EQUITY = []
log('\n########## (C) 描述性：超额自付占家庭收入中位数之比，按收入五分位 ##########')
for db in MAIN:
    d = DATA[db].copy()
    if db == 'share':
        d = d[d.wave == 1]                     # 收入口径跨波不可比，仅 w1（诊断③）
    inc20 = d['hhinc_2020intl'].astype(float)
    for q in (1, 2, 3, 4, 5):
        s = d[(d.inc_q5 == q) & (inc20 > 0) & d.oop_2020intl.notna()]
        if len(s) < 200:
            continue
        w = s.weight.clip(lower=0.01)
        a1 = s[s.arth == 1]; a0 = s[s.arth == 0]
        if len(a1) < 50 or len(a0) < 50:
            continue
        m1 = float(np.average(a1.oop_2020intl, weights=a1.weight.clip(lower=0.01)))
        m0 = float(np.average(a0.oop_2020intl, weights=a0.weight.clip(lower=0.01)))
        med_inc = float(np.median(s.hhinc_2020intl))
        excess = m1 - m0
        pct = 100.0 * excess / med_inc if med_inc > 0 else np.nan
        EQUITY.append(dict(db=db, quintile=q, n=len(s), n_arth1=len(a1),
                           mean_oop_arth1_2020intl=m1, mean_oop_arth0_2020intl=m0,
                           excess_2020intl=excess, median_income_2020intl=med_inc,
                           excess_pct_income=pct, note=('SHARE w1 only' if db == 'share' else '')))
        log(f'  {db:6s} Q{q} n={len(s):>7,} 关节炎组均值={m1:>8.1f} 对照组={m0:>8.1f} '
            f'超额={excess:>7.1f} Int$ 收入中位数={med_inc:>10.1f} 超额占收入={pct:.3f}%')
    pd.DataFrame(EQUITY).to_csv(os.path.join(OUT, '41_ses_equity.csv'),
                                index=False, encoding='utf-8-sig', float_format='%.6f')

eq = pd.DataFrame(EQUITY)
ratios = []
for db in MAIN:
    r = eq[eq.db == db]
    if set([1, 5]).issubset(set(r.quintile)):
        p1 = float(r[r.quintile == 1].excess_pct_income.iloc[0])
        p5 = float(r[r.quintile == 5].excess_pct_income.iloc[0])
        if p5 > 0:
            ratios.append(dict(db=db, q1_pct=p1, q5_pct=p5, ratio_q1_q5=p1 / p5))
pd.DataFrame(ratios).to_csv(os.path.join(OUT, '41_ses_equity_ratio.csv'),
                            index=False, encoding='utf-8-sig', float_format='%.6f')

# ---------------------------------------------------------------- 正式检验汇总
T = []
def T_(tid, name, val, lo, hi, p, note=''):
    T.append(dict(test=tid, label=name, estimate=val, lo=lo, hi=hi, p=p, note=note))

for oc in OUTCOMES:
    for ax in AXES:
        r = [x for x in pool_int if x['outcome'] == oc and x['axis'] == ax]
        if r:
            r = r[0]
            T_('T_%s_%s' % ('P1' if oc.startswith('P1') else 'P2inc',
                            'income' if ax == 'income_quintile' else 'education'),
               'Interaction, ratio of effects per SES step', r['pooled_effect'],
               r['lo'], r['hi'], r['p'], 'BH q=%.4f; k=%d; I2=%.1f%%' % (r['bh_q'], r['k_meta'], r['I2']))
# 分层方向一致性：P1 各层合并 OR>1 的个数
for ax, A in AXES.items():
    sub = [x for x in POOLED if x['outcome'] == 'P1_any_oop' and x['axis'] == ax]
    npos = sum(1 for x in sub if x['lo'] > 1)
    T_('T_sign_%s' % ax, 'P1 pooled OR with lower 95% bound >1, by stratum',
       npos, len(sub), None, np.nan, '%d of %d strata' % (npos, len(sub)))
# Q1/Q5 描述性比
if ratios:
    rr = np.array([x['ratio_q1_q5'] for x in ratios])
    T_('T_equity_ratio', 'Median Q1/Q5 ratio of excess OOP as % of income',
       float(np.median(rr)), float(rr.min()), float(rr.max()), np.nan,
       'descriptive, unadjusted; k=%d cohorts; SHARE w1 only' % len(rr))
# 分层间异质性（各层合并 log 效应的 Q 检验）
for oc in OUTCOMES:
    for ax in AXES.items():
        pass
pd.DataFrame(T).to_csv(os.path.join(OUT, '41_ses_tests.csv'),
                       index=False, encoding='utf-8-sig', float_format='%.6f')

# Figure 5 绘图数据
FIG = []
for x in POOLED:
    FIG.append(dict(outcome=x['outcome'], axis=x['axis'], stratum=x['stratum'],
                    effect=x['pooled_effect'], lo=x['lo'], hi=x['hi'],
                    I2=x['I2'], k=x['k_meta']))
pd.DataFrame(FIG).to_csv(os.path.join(OUT, '41_ses_figure.csv'),
                         index=False, encoding='utf-8-sig', float_format='%.6f')

log('\nDONE | strata=%d pooled=%d interaction=%d equity=%d tests=%d' %
    (len(STRATA), len(POOLED), len(INTER), len(EQUITY), len(T)))
