# -*- coding: utf-8 -*-
"""方向 A / 任务 11b：口径修正 + 全套敏感性。
背景：20 的主模型发现 SHARE w2/w5/w6 的 B10/B40 事件率近 0；核查证明
      hh{w}itothhinc 对同一批人是 w1 hh1itot 的 10.32 倍（w2/w5/w6 一致），
      系收入变量口径不同，而非经济变化 -> 阈值结局对分母缩放不稳健。
修正：
  1) 新增 P2inc：log(自付金额) ~ arth + log(家庭收入) + 协变量（正值且有正收入），
     对分母的常数缩放稳健，作为「相对负担」主结局。
  2) B10/B40 主 meta 排除 SHARE w2/w5/w6（仅保留 w1）；另给经验因子 /10.3178 校正版作对照。
敏感性：排除插补 / 1-99% 缩尾 / 未加权 / 最小调整 / Gamma GLM / 消费 CHE / CHARLS 扩展库。
输出：21_a1_revised_sensitivity.csv、21_a1_revised_meta.csv、
      21_a1_results.txt、21_forest_revised.csv
"""
import os, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '21_a1_results.txt')
MAIN = ['mhas','hrs','share','lasi']
SHARE_FACTOR = 10.3178
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def design(d, db, minimal=False, loginc=False):
    X = pd.DataFrame(index=d.index)
    X['arth'] = d['arth'].astype(float)
    X['age10'] = (d['age']-70.0)/10.0
    X['female'] = d['female']; X['married'] = d['married']
    X['shlt'] = d['shlt']; X['adl_any'] = d['adl_any']
    if not minimal:
        X['diabe']=d['diabe']; X['hibpe']=d['hibpe']; X['stroke']=d['stroke']
        if d['rural'].nunique() > 1: X['rural']=d['rural']
    if loginc:
        X['log_hhinc'] = np.log(d['hhinc'].clip(lower=1))
    for c, pre in [('educ','edu'),('wave','wv')]:
        X = pd.concat([X, pd.get_dummies(d[c].astype('Int64').astype(str),
                                         prefix=pre, drop_first=True)], axis=1)
    if db=='share' and not minimal and d['iso3'].nunique() > 1:
        X = pd.concat([X, pd.get_dummies(d['iso3'].astype(str), prefix='cty', drop_first=True)], axis=1)
    X = X.astype(float)
    keep = [c for c in X.columns if X[c].nunique(dropna=False) > 1]
    return sm.add_constant(X[keep], has_constant='add')

def fit(y, X, w, g, kind='glm'):
    try:
        if kind=='glm':
            r = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w).fit(
                cov_type='cluster', cov_kwds={'groups':g}, maxiter=100)
        elif kind=='wls':
            r = sm.WLS(y, X, weights=w).fit(cov_type='cluster', cov_kwds={'groups':g})
        else:
            r = sm.GLM(y, X, family=sm.families.Gamma(sm.families.links.Log()),
                       freq_weights=w).fit(cov_type='cluster', cov_kwds={'groups':g}, maxiter=100)
        return r, 'cluster'
    except Exception as e:
        if kind=='glm':
            r = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w).fit(maxiter=100)
        elif kind=='wls':
            r = sm.WLS(y, X, weights=w).fit(cov_type='HC0')
        else:
            r = sm.GLM(y, X, family=sm.families.Gamma(sm.families.links.Log()),
                       freq_weights=w).fit(maxiter=100)
        return r, 'fallback:'+type(e).__name__

def row(res, cov, db, oc, tag, n, n1, g):
    b=float(res.params['arth']); se=float(res.bse['arth'])
    return dict(set=tag, db=db, outcome=oc, beta=b, se=se, effect=float(np.exp(b)),
                lo=float(np.exp(b-1.96*se)), hi=float(np.exp(b+1.96*se)),
                p=float(2*stats.norm.sf(abs(b/se))), n=int(n), n_arth1=int(n1),
                n_cluster=int(g.nunique()), cov=cov)

def meta_dl(rows):
    y=np.array([r['beta'] for r in rows]); se=np.array([r['se'] for r in rows]); k=len(y)
    w=1/se**2; mf=(w*y).sum()/w.sum(); Q=float((w*(y-mf)**2).sum())
    C=w.sum()-(w**2).sum()/w.sum(); tau2=max(0.0,(Q-(k-1))/C) if C>0 else 0.0
    wr=1/(se**2+tau2); mu=float((wr*y).sum()/wr.sum()); sm_=float(np.sqrt(1/wr.sum()))
    # 95% 预测区间：Higgins-Thompson-Spiegelhalter，t 分布 df=k-2（k=2 时退化为正态）
    se_pi=float(np.sqrt(tau2+sm_**2)); tpi=float(stats.t.ppf(.975,k-2)) if k>2 else 1.96
    return dict(k=k, pooled_effect=float(np.exp(mu)), lo=float(np.exp(mu-1.96*sm_)),
                hi=float(np.exp(mu+1.96*sm_)), p=float(2*stats.norm.sf(abs(mu/sm_))),
                pi_lo=float(np.exp(mu-tpi*se_pi)), pi_hi=float(np.exp(mu+tpi*se_pi)),
                Q=Q, Q_p=float(stats.chi2.sf(Q,k-1)) if k>1 else None,
                I2=max(0.0,(Q-(k-1))/Q*100) if Q>0 else 0.0, tau2=tau2)

def one(db, tag, d, *, w_on=True, minimal=False, winsor=False, gamma=False,
        burden_mode='exclude_share_w2plus', outcomes=('P1','P2','P2inc','B10','B40')):
    out=[]
    d=d.copy()
    d['pos']=(d['oop_annual_lcu']>0).astype(float)
    amt=d['oop_2020intl'].astype(float)
    if winsor and (amt>0).any():
        pos=amt>0
        lo,hi=amt.loc[pos].quantile([0.01,0.99])
        amt.loc[pos]=amt.loc[pos].clip(lower=lo, upper=hi)  # 只缩正值；零值仍为零
    d['logoop']=np.where(amt>0, np.log(amt.clip(lower=1e-9)), np.nan)
    d['amt_win']=amt
    w=d['weight'].clip(lower=0.01) if w_on else pd.Series(1.0, index=d.index)
    g=d['id'].astype(str)
    # 负担比（按 burden_mode 修正 SHARE 分母）
    inc=d['hhinc'].astype(float)
    if burden_mode=='scale10' and db=='share':
        inc=inc.where(d['wave']==1, inc/SHARE_FACTOR)
    ratio=d['oop_annual_lcu']/inc.where(inc>0)   # 分子分母均为本币年度口径
    b10=(ratio>=0.10).astype(float); b40=(ratio>=0.40).astype(float)
    b10[ratio.isna()]=np.nan; b40[ratio.isna()]=np.nan
    if burden_mode=='exclude_share_w2plus' and db=='share':
        bad=d['wave']!=1; b10[bad]=np.nan; b40[bad]=np.nan
    d['b10']=b10; d['b40']=b40
    # P1
    if 'P1' in outcomes:
        r,c=fit(d['pos'], design(d,db,minimal), w, g)
        out.append(row(r,c,db,'P1_any_oop',tag,len(d),(d.arth==1).sum(),g))
    # P2 / P2inc / Gamma
    sub=d[d['logoop'].notna()]
    if 'P2' in outcomes and len(sub)>100:
        r,c=fit(sub['logoop'], design(sub,db,minimal), w.loc[sub.index], g.loc[sub.index], 'wls')
        out.append(row(r,c,db,'P2_amount_log',tag,len(sub),(sub.arth==1).sum(),g.loc[sub.index]))
    if 'P2inc' in outcomes:
        s2=sub[sub['hhinc']>0]
        if len(s2)>100:
            r,c=fit(s2['logoop'], design(s2,db,minimal,loginc=True),
                    w.loc[s2.index], g.loc[s2.index], 'wls')
            out.append(row(r,c,db,'P2inc_amount_log_adj_income',tag,len(s2),(s2.arth==1).sum(),g.loc[s2.index]))
    if gamma:
        sg=sub[sub['amt_win']>0]
        if len(sg)>100:
            try:
                r,c=fit(sg['amt_win'], design(sg,db,minimal), w.loc[sg.index],
                        g.loc[sg.index], 'gamma')
                out.append(row(r,c,db,'P2_gamma_glm',tag,len(sg),(sg.arth==1).sum(),g.loc[sg.index]))
            except Exception as e:
                log(f"    {db}/{tag} Gamma 失败 {type(e).__name__}")
    # B10 / B40
    for ycol,lab in [('b10','B10_oop_ge10pct_income'),('b40','B40_oop_ge40pct_income')]:
        if lab.split('_')[0] not in [x.split('_')[0] for x in outcomes] and False: continue
        s=d[d[ycol].notna()]
        if len(s)<200: continue
        r,c=fit(s[ycol], design(s,db,minimal), w.loc[s.index], g.loc[s.index])
        out.append(row(r,c,db,lab,tag,len(s),(s.arth==1).sum(),g.loc[s.index]))
    return out

log("方向 A / 任务 11b：口径修正 + 敏感性｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log(f"SHARE 收入经验校准因子 = {SHARE_FACTOR}（w2/w5/w6 对 w1 同人比值中位数，仅作敏感性）")
log("P2inc = log(自付) ~ arth + log(家庭收入) + 协变量；对分母常数缩放稳健。\n")

DATA={db:pd.read_csv(os.path.join(OUT,f'18_data_{db}.csv'),low_memory=False)
      for db in ['mhas','hrs','share','lasi','charls']}
ALL=[]
SETS=[
 dict(tag='main_revised', note='主修正：加权、完整协变量、B10/B40 排除 SHARE w2/w5/w6'),
 dict(tag='noimp', note='排除插补样本', filt=lambda d:d.imputed==0),
 dict(tag='winsor', note='正值金额按库 1/99 缩尾', winsor=True),
 dict(tag='unweighted', note='不使用抽样权重', w_on=False),
 dict(tag='minimal', note='最小调整（年龄/性别/婚姻/自评健康/ADL/波次）', minimal=True),
 dict(tag='gamma', note='P2 改用 Gamma GLM(log link)', gamma=True),
 dict(tag='share_scale10', note='SHARE w2/w5/w6 收入 /10.3178 后重算阈值', burden_mode='scale10'),
]
for cfg in SETS:
    tag=cfg['tag']; log(f"\n########## {tag} ########## {cfg['note']}")
    for db in MAIN:
        d=DATA[db]
        if 'filt' in cfg: d=d[cfg['filt'](d)]
        try:
            r=one(db,tag,d,**{k:v for k,v in cfg.items() if k in
                ('w_on','minimal','winsor','gamma','burden_mode')})
            ALL.extend(r)
            p1=[x for x in r if x['outcome']=='P1_any_oop']
            log(f"  {db:<6s} n={r[0]['n']:,} " + ' | '.join(
                f"{x['outcome'].split('_')[0]}={x['effect']:.3f}({x['lo']:.3f}-{x['hi']:.3f})"
                for x in r))
        except Exception as e:
            log(f"  {db}: 失败 {type(e).__name__} {str(e)[:150]}")

# 消费 CHE 敏感性（仅可得子样本，不并入主 meta）
log("\n########## che_cons ########## WHO 消费分母 CHE（仅可得波次，单独报告）")
for db in ['mhas','share','lasi','charls']:
    d=DATA[db].copy()
    d=d[d['che10_cons'].notna()]
    if db=='share': d=d[d['wave']==1]
    if len(d)<500: continue
    w=d['weight'].clip(lower=0.01); g=d['id'].astype(str)
    r,c=fit(d['che10_cons'], design(d,db), w, g)
    ALL.append(row(r,c,db,'CHE10_consumption_denominator','che_cons',len(d),
                   (d.arth==1).sum(),g))
    log(f"  {db:<6s} n={len(d):,} OR={np.exp(r.params['arth']):.3f} "
        f"({np.exp(r.params['arth']-1.96*r.bse['arth']):.3f}-{np.exp(r.params['arth']+1.96*r.bse['arth']):.3f})")

# CHARLS 扩展库（自建总额，不进主 meta）
log("\n########## charls_ext ########## CHARLS 扩展库（自建年化总额，不进主 meta）")
r=one('charls','charls_ext',DATA['charls'],burden_mode='none')
ALL.extend(r)
log("  " + ' | '.join(f"{x['outcome'].split('_')[0]}={x['effect']:.3f}"
                     f"({x['lo']:.3f}-{x['hi']:.3f})" for x in r))

# meta
metas=[]
for tag in sorted(set(x['set'] for x in ALL)):
    for oc in sorted(set(x['outcome'] for x in ALL)):
        rows=[x for x in ALL if x['set']==tag and x['outcome']==oc and x['db'] in MAIN]
        if len(rows)>=2:
            m=meta_dl(rows); m.update(set=tag, outcome=oc); metas.append(m)
log("\n########## 主要 meta 结果 ##########")
for m in metas:
    if m['set'] in ('main_revised','noimp','share_scale10'):
        log(f"  {m['set']:<16s} {m['outcome']:<32s} {m['pooled_effect']:.3f} "
            f"({m['lo']:.3f}-{m['hi']:.3f}) I2={m['I2']:.1f}% k={m['k']}")

with open(os.path.join(OUT,'21_a1_revised_sensitivity.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(ALL).to_csv(f,index=False,float_format='%.6f')
with open(os.path.join(OUT,'21_a1_revised_meta.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(metas).to_csv(f,index=False,float_format='%.6f')
fc=pd.DataFrame([dict(set=x['set'],db=x['db'],outcome=x['outcome'],effect=x['effect'],
                      lo=x['lo'],hi=x['hi'],n=x['n']) for x in ALL] +
                [dict(set=m['set'],db='POOLED (RE)',outcome=m['outcome'],
                      effect=m['pooled_effect'],lo=m['lo'],hi=m['hi'],n=None) for m in metas])
with open(os.path.join(OUT,'21_forest_revised.csv'),'w',encoding='utf-8-sig',newline='') as f:
    fc.to_csv(f,index=False,float_format='%.4f')
log(f"\nDONE: {len(ALL)} 条估计，{len(metas)} 条 meta")
