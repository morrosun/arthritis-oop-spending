# -*- coding: utf-8 -*-
"""A1 遗留诊断②：B40（OOP/收入≥40%）校正后方向反转的驱动因素。

事实：粗率关节炎组更高，但全校正后 HRS OR=0.908 (0.850–0.970)、
      SHARE OR=0.775 (0.546–1.100)，MHAS/LASI 为 1.201/1.276，合并 1.053 (ns)。
本脚本回答：反转由「过度调整 / 收入构成 / 极端支出 / 权重 / 特定波次」哪项驱动？
方法：
  (A) 嵌套调整序列 L0…L7：逐组加协变量，定位 OR 从 >1 跌破 1 的那一步。
  (B) 分层分析：收入五分位、年龄、性别、共病数、自评健康、极端支出、
      排除插补、未加权、逐波；均用完整协变量模型（层内剔除分层变量）。
  (C) 粗 2×2 OR 与粗事件率，作为未校正参照。
输出：31_diag_b40_reversal.csv / 31_diag_b40_reversal.txt / 31_diag_b40_crude.csv
"""
import os, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
src = open(os.path.join(OUT, '21_fit_a1_revised.py'), encoding='utf-8').read()
head = src.split('log("方向 A / 任务 11b')[0]
exec(compile(head, '21_fit_a1_revised.py', 'exec'), globals())
TXT = os.path.join(OUT, '31_diag_b40_reversal.txt')
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

MAIN = ['mhas','hrs','share','lasi']
DATA = {db: pd.read_csv(os.path.join(OUT, f'18_data_{db}.csv'), low_memory=False)
        for db in MAIN}

# ---------- 结局构造（与 21 主分析完全一致） ----------
def prepare(db):
    d = DATA[db].copy()
    inc = d['hhinc'].astype(float)
    ratio = d['oop_annual_lcu'] / inc.where(inc > 0)
    for thr, name in [(0.10,'b10'), (0.40,'b40')]:
        y = (ratio >= thr).astype(float); y[ratio.isna()] = np.nan
        if db == 'share':                       # 主分析口径：SHARE 仅 w1
            y[d['wave'] != 1] = np.nan
        d[name] = y
    d['log_hhinc'] = np.log(inc.clip(lower=1))
    d['age10'] = (d['age'] - 70.0)/10.0
    # 收入五分位（库×波内，按秩避免重复值导致 qcut 失败）
    d['inc_q'] = np.nan
    ok = inc > 0
    d.loc[ok,'inc_q'] = d.loc[ok].groupby('wave')['hhinc'].rank(pct=True)
    d['inc_q5'] = np.ceil(d['inc_q']*5).clip(1,5)
    d['comorb_n'] = d[['diabe','hibpe','stroke']].sum(axis=1).clip(0,2)
    d['age_grp'] = pd.cut(d['age'], [0,65,75,200], labels=['<65','65-74','75+'], right=False).astype(str)
    d['shlt_grp'] = np.where(d['shlt']>=4,'fair/poor','good+')
    p99 = d.loc[d.oop_annual_lcu>0,'oop_annual_lcu'].quantile(0.99)
    d['extreme'] = (d.oop_annual_lcu > p99).astype(float)
    return d, p99

PREP = {db: prepare(db) for db in MAIN}
P99 = {db: PREP[db][1] for db in MAIN}
D = {db: PREP[db][0] for db in MAIN}

# ---------- 可配置设计矩阵 ----------
GROUPS = {
 'base':    lambda d,db: pd.DataFrame({'arth': d['arth'].astype(float)}, index=d.index),
 'demog':   lambda d,db: pd.DataFrame({'age10':d['age10'],'female':d['female'],
                                       'married':d['married']}, index=d.index),
 'educ':    lambda d,db: pd.get_dummies(d['educ'].astype('Int64').astype(str), prefix='edu', drop_first=True),
 'wave':    lambda d,db: pd.get_dummies(d['wave'].astype('Int64').astype(str), prefix='wv', drop_first=True),
 'health':  lambda d,db: pd.DataFrame({'shlt':d['shlt'],'adl_any':d['adl_any']}, index=d.index),
 'comorb':  lambda d,db: pd.DataFrame({'diabe':d['diabe'],'hibpe':d['hibpe'],'stroke':d['stroke']}, index=d.index),
 'rural':   lambda d,db: pd.DataFrame({'rural':d['rural']}, index=d.index),
 'country': lambda d,db: pd.get_dummies(d['iso3'].astype(str), prefix='cty', drop_first=True),
 'loginc':  lambda d,db: pd.DataFrame({'log_hhinc':d['log_hhinc']}, index=d.index),
}
LEVELS = [
 ('L0_crude',            ['base']),
 ('L1_demog',            ['base','demog','educ']),
 ('L2_waveFE',           ['base','demog','educ','wave']),
 ('L3_health',           ['base','demog','educ','wave','health']),
 ('L4_comorb',           ['base','demog','educ','wave','health','comorb']),
 ('L5_full_main',        ['base','demog','educ','wave','health','comorb','rural','country']),
 ('L6_full_plus_loginc', ['base','demog','educ','wave','health','comorb','rural','country','loginc']),
 ('L7_no_health',        ['base','demog','educ','wave','comorb','rural','country']),
]

def build_X(d, db, groups, drop=None):
    parts = []
    for g in groups:
        if g == drop: continue
        p = GROUPS[g](d, db)
        p.index = d.index
        parts.append(p)
    X = pd.concat(parts, axis=1).astype(float)
    keep = [c for c in X.columns if X[c].nunique(dropna=False) > 1]
    X = X[keep]
    if 'arth' not in X.columns: X.insert(0,'arth', d['arth'].astype(float).values)
    return sm.add_constant(X, has_constant='add')

def run(d, db, ycol, groups, tag, stratum='ALL', drop=None, weighted=True, extra=None):
    s = d[d[ycol].notna()]
    if len(s) < 300 or s[ycol].nunique() < 2: return None
    X = build_X(s, db, groups, drop=drop)
    w = s['weight'].clip(lower=0.01) if weighted else pd.Series(1.0, index=s.index)
    g = s['id'].astype(str)
    r, cov = fit(s[ycol], X, w, g)
    row_ = row(r, cov, db, ycol, tag, len(s), (s.arth==1).sum(), g)
    row_['tag'] = tag
    row_.update(stratum=stratum, level='+'.join(groups), weighted=weighted,
                n_events=int(s[ycol].sum()),
                rate_arth1=float(s.loc[s.arth==1,ycol].mean()),
                rate_arth0=float(s.loc[s.arth==0,ycol].mean()))
    if extra: row_.update(extra)
    return row_

def crude_or(d, db, ycol):
    s = d[d[ycol].notna()]
    a=((s.arth==1)&(s[ycol]==1)).sum(); b=((s.arth==1)&(s[ycol]==0)).sum()
    c=((s.arth==0)&(s[ycol]==1)).sum(); e=((s.arth==0)&(s[ycol]==0)).sum()
    if min(a,b,c,e)==0: a,b,c,e=[x+0.5 for x in (a,b,c,e)]
    o=(a*e)/(b*c); se=np.sqrt(1/a+1/b+1/c+1/e)
    return dict(db=db,outcome=ycol,n=len(s),rate_arth1=a/(a+b),rate_arth0=c/(c+e),
                crude_or=o,crude_lo=np.exp(np.log(o)-1.96*se),crude_hi=np.exp(np.log(o)+1.96*se),
                n_arth1=int((s.arth==1).sum()))

log("A1 遗留诊断②：B40 校正后方向反转｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("结局：OOP/家庭收入 >=10% (B10) 与 >=40% (B40)；SHARE 仅 w1（主分析口径）。")
log("所有 OR 为加权 GLM-binomial + 个体 ID 聚类稳健 SE，除非标注 unweighted。\n")

RES, CRUDE = [], []
for db in MAIN:
    d = D[db]
    for ycol in ['b10','b40']:
        CRUDE.append(crude_or(d, db, ycol))
    log(f"########## {db} ##########  n={len(d):,}  P99(OOP本币)={P99[db]:,.0f}")
    for ycol in ['b10','b40']:
        cr = [x for x in CRUDE if x['db']==db and x['outcome']==ycol][0]
        log(f"  粗率 {ycol}: arth1={100*cr['rate_arth1']:.2f}%  arth0={100*cr['rate_arth0']:.2f}%  "
            f"粗OR={cr['crude_or']:.3f} ({cr['crude_lo']:.3f}-{cr['crude_hi']:.3f})")

# ---------- (A) 嵌套调整序列 ----------
log("\n########## (A) 嵌套调整序列 ##########")
for db in MAIN:
    for ycol in ['b10','b40']:
        seq=[]
        for tag, groups in LEVELS:
            r = run(D[db], db, ycol, groups, tag)
            if r: RES.append(r); seq.append(r)
        log(f"  {db:<6s} {ycol}: " + ' → '.join(f"{x['tag']}={x['effect']:.3f}" for x in seq))

# ---------- (B) 分层 ----------
log("\n########## (B) 分层／敏感性（B40，完整协变量 L5）##########")
FULL = LEVELS[5][1]
STRATA = [
 ('income_q',  'inc_q5',      {1:'Q1最低',2:'Q2',3:'Q3',4:'Q4',5:'Q5最高'}, 'loginc', None),
 ('age_grp',   'age_grp',     None, None, None),
 ('sex',       'female',      {0:'男',1:'女'}, None, None),
 ('comorb_n',  'comorb_n',    {0:'0种',1:'1种',2:'>=2种'}, None, None),
 ('shlt_grp',  'shlt_grp',    None, None, None),
]
for db in MAIN:
    d = D[db]
    for name, col, mapping, drop, _ in STRATA:
        vals = sorted(d[col].dropna().unique())
        for v in vals:
            sub = d[d[col]==v]
            lab = mapping.get(v, str(v)) if mapping else str(v)
            r = run(sub, db, 'b40', FULL, f'{name}:{lab}', stratum=f'{name}={lab}', drop=drop)
            if r: RES.append(r)
            if r: log(f"  {db:<6s} {name}={lab:<10s} n={r['n']:>7,} 事件率={100*r['n_events']/r['n']:>5.2f}%  "
                      f"OR={r['effect']:.3f} ({r['lo']:.3f}-{r['hi']:.3f})")
    # 二值/子集敏感性
    for tag, filt, drop in [
        ('exclude_extreme_P99', d.extreme==0, None),
        ('exclude_imputed',     d.imputed==0, None),
        ('unweighted',          pd.Series(True,index=d.index), None),
        ('exclude_inc_bottom10',d.inc_q>0.10, None),
        ('exclude_inc_top10',   d.inc_q<=0.90, None),
    ]:
        sub = d[filt]
        r = run(sub, db, 'b40', FULL, tag, stratum=tag, drop=drop,
                weighted=(tag!='unweighted'))
        if r: RES.append(r)
        if r: log(f"  {db:<6s} {tag:<22s} n={r['n']:>7,} 事件率={100*r['n_events']/r['n']:>5.2f}%  "
                  f"OR={r['effect']:.3f} ({r['lo']:.3f}-{r['hi']:.3f})")

# ---------- (C) 逐波 ----------
log("\n########## (C) 逐波 B40（完整协变量 L5，波次哑变量自动退化为常数）##########")
for db in MAIN:
    d = D[db]
    for w in sorted(d.wave.unique()):
        sub = d[d.wave==w]
        r = run(sub, db, 'b40', FULL, f'wave{w}', stratum=f'wave={w}')
        if r: RES.append(r)
        if r and db=='hrs':
            log(f"  {db:<6s} w{w:<2d} n={r['n']:>7,} 事件率={100*r['n_events']/r['n']:>5.2f}%  "
                f"OR={r['effect']:.3f} ({r['lo']:.3f}-{r['hi']:.3f})")
    if db!='hrs':
        hs=[x for x in RES if x['db']==db and x['tag'].startswith('wave')]
        log(f"  {db:<6s} " + ' | '.join(f"w{x['stratum'].split('=')[1]}:{x['effect']:.3f}" for x in hs))

with open(os.path.join(OUT,'31_diag_b40_reversal.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(RES).to_csv(f,index=False,float_format='%.6f')
with open(os.path.join(OUT,'31_diag_b40_crude.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(CRUDE).to_csv(f,index=False,float_format='%.6f')
log(f"\nDONE: {len(RES)} 条分层/嵌套估计，{len(CRUDE)} 条粗率")
