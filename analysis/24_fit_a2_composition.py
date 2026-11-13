# -*- coding: utf-8 -*-
"""方向 A / A2：支出结构分解（精确会计分解，非近似）。
数据：23_data_components.csv，353,111 行、4 库 15 波，分项加总 == 年化总额（100% 精确）。
对每个 (库 × 支出大类)：
  Part1 logit 该项有无支出 -> OR
  Part2 log-OLS 该项支出金额（有支出者） -> 金额比
  份额 OLS（在 oop>0 样本） -> 份额差（百分点）
  g-computation -> 归因自付金额（2020 国际元/年），占总额归因金额的 %
按库估计；OR/金额比在可得主库 >=3 时做 DL 随机效应合并（k=2 不合并）。
HRS 无任何支出分项，不进 A2；CHARLS 为扩展库。
输出：24_a2_results.txt / 24_a2_component_results.csv / 24_a2_meta.csv /
      24_a2_attributable.csv / 24_a2_shares.csv / 24_a2_forest.csv
"""
import os, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '24_a2_results.txt')
CATS = ['drug','outpatient','inpatient','dental','other']
MAIN = ['mhas','share','lasi']
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT,'w',encoding='utf-8') as f: f.write('\n'.join(lines))

def design(d, db):
    X = pd.DataFrame(index=d.index)
    X['arth']=d['arth'].astype(float)
    X['age10']=(d['age']-70.0)/10.0
    for c in ['female','married','shlt','adl_any','diabe','hibpe','stroke']:
        X[c]=d[c]
    if d['rural'].nunique()>1: X['rural']=d['rural']
    for c,pre in [('educ','edu'),('wave','wv')]:
        X=pd.concat([X,pd.get_dummies(d[c].astype('Int64').astype(str),prefix=pre,drop_first=True)],axis=1)
    if db=='share' and d['iso3'].nunique()>1:
        X=pd.concat([X,pd.get_dummies(d['iso3'].astype(str),prefix='cty',drop_first=True)],axis=1)
    X=X.astype(float)
    keep=[c for c in X.columns if X[c].nunique(dropna=False)>1]
    return sm.add_constant(X[keep],has_constant='add')

def fit(y,X,w,g,kind='glm'):
    try:
        if kind=='glm':
            return sm.GLM(y,X,family=sm.families.Binomial(),freq_weights=w).fit(
                cov_type='cluster',cov_kwds={'groups':g},maxiter=100),'cluster'
        return sm.WLS(y,X,weights=w).fit(cov_type='cluster',cov_kwds={'groups':g}),'cluster'
    except Exception as e:
        if kind=='glm':
            return sm.GLM(y,X,family=sm.families.Binomial(),freq_weights=w).fit(maxiter=100),'HC0_fb'
        return sm.WLS(y,X,weights=w).fit(cov_type='HC0'),'HC0_fb'

def eff(res,oc,db,cat,n,n1,clus,tag='main'):
    b=float(res.params['arth']); se=float(res.bse['arth'])
    return dict(set=tag,db=db,cat=cat,outcome=oc,beta=b,se=se,effect=float(np.exp(b)),
                lo=float(np.exp(b-1.96*se)),hi=float(np.exp(b+1.96*se)),
                p=float(2*stats.norm.sf(abs(b/se))),n=int(n),n_arth1=int(n1),
                n_cluster=int(clus),unit='OR/ratio')

def meta_dl(rows):
    y=np.array([r['beta'] for r in rows]); se=np.array([r['se'] for r in rows]); k=len(y)
    w=1/se**2; mf=(w*y).sum()/w.sum(); Q=float((w*(y-mf)**2).sum())
    C=w.sum()-(w**2).sum()/w.sum(); tau2=max(0.,(Q-(k-1))/C) if C>0 else 0.
    wr=1/(se**2+tau2); mu=float((wr*y).sum()/wr.sum()); s=float(np.sqrt(1/wr.sum()))
    return dict(k=k,pooled_effect=float(np.exp(mu)),lo=float(np.exp(mu-1.96*s)),
                hi=float(np.exp(mu+1.96*s)),p=float(2*stats.norm.sf(abs(mu/s))),
                Q=Q,Q_p=float(stats.chi2.sf(Q,k-1)),I2=max(0.,(Q-(k-1))/Q*100) if Q>0 else 0.,
                tau2=tau2)

log("方向 A / A2：支出结构分解｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("精确会计恒等：Σ 分项 == harmonized 年化总额（23_component_check.txt：15/15 库×波 100%）")
log("每个分项独立跑两部分模型 + g-comp；归因金额按分项加总回总额归因金额。")
log("仅保留该库该波**实际询问了该分项**的行（avail_*==1），避免把'未问'误当'零支出'。\n")

D=pd.read_csv(os.path.join(OUT,'23_data_components.csv'),low_memory=False)
D=D[D['exact']==1].copy()
log(f"加载 {len(D):,} 行（exact=1）｜库={sorted(D.db.unique())}\n")
G=pd.read_csv(os.path.join(OUT,'22_1a_gcomp.csv'))
TOTAL={r.db:r.attributable_oop_2020intl for r in G.itertuples()}

rows,attr,shares=[],[],[]
for db in ['mhas','share','lasi','charls']:
    Dd=D[D.db==db]
    log(f"########## {db} ########## 总额归因 = {TOTAL.get(db,float('nan')):,.1f} 2020国际元/年")
    for cat in CATS+['folk']:
        acol='avail_'+cat; vcol='cat_'+cat; icol=cat+'_2020intl'
        if acol not in Dd.columns or vcol not in Dd.columns: continue
        d=Dd[Dd[acol]==1].copy()
        if len(d)<500 or int((d[vcol]>0).sum())<100:
            log(f"  {cat:<11s} SKIP (n={len(d):,}, 正支出={int((d[vcol]>0).sum()):,})"); continue
        d=d.dropna(subset=['arth','age','female','educ','married','shlt','adl_any',
                           'diabe','hibpe','stroke','weight','deflator_2020'])
        if len(d)<500: continue
        w=d['weight'].clip(lower=0.01); g=d['id'].astype(str)
        X=design(d,db)
        # ---- Part1: 该项有无支出 ----
        y1=(d[vcol]>0).astype(float)
        r1,c1=fit(y1,X,w,g,'glm')
        rows.append(eff(r1,'any_'+cat,db,cat,len(d),int((d.arth==1).sum()),g.nunique()))
        # ---- Part2: 有支出者金额 ----
        sub=d[(d[vcol]>0)&(d[icol]>0)].copy()
        r2=None
        if len(sub)>100:
            X2=design(sub,db); w2=sub['weight'].clip(lower=0.01); g2=sub['id'].astype(str)
            y2=np.log(sub[icol])
            r2,c2=fit(y2,X2,w2,g2,'wls')
            rows.append(eff(r2,'amount_'+cat,db,cat,len(sub),int((sub.arth==1).sum()),g2.nunique()))
        # ---- 份额（oop>0 样本的加权描述 + OLS 差） ----
        sp=d[d['oop_annual_lcu']>0].copy()
        if len(sp)>200:
            sp['share']=sp[vcol]/sp['oop_annual_lcu']
            ws=sp['weight'].clip(lower=0.01); gs=sp['id'].astype(str)
            s1=float(np.average(sp.loc[sp.arth==1,'share'],weights=sp.loc[sp.arth==1,'weight'].clip(lower=.01)))
            s0=float(np.average(sp.loc[sp.arth==0,'share'],weights=sp.loc[sp.arth==0,'weight'].clip(lower=.01)))
            Xs=design(sp,db)
            rs,cs=fit(sp['share'],Xs,ws,gs,'wls')
            b=float(rs.params['arth']); se=float(rs.bse['arth'])
            shares.append(dict(db=db,cat=cat,n=len(sp),share_arth1_pct=round(100*s1,2),
                               share_arth0_pct=round(100*s0,2),
                               diff_pp=round(100*b,2),lo_pp=round(100*(b-1.96*se),2),
                               hi_pp=round(100*(b+1.96*se),2),
                               p=float(2*stats.norm.sf(abs(b/se))),cov=cs))
            log(f"  {cat:<11s} 份额 arth1={100*s1:5.1f}% vs arth0={100*s0:5.1f}% "
                f"校正差={100*b:+5.2f}pp ({100*(b-1.96*se):+.2f},{100*(b+1.96*se):+.2f})")
        # ---- g-comp 分项归因金额 ----
        if r2 is not None:
            smear=float(np.mean(np.exp(r2.resid)))
            X1=X.copy(); X1['arth']=1.0
            X0=X.copy(); X0['arth']=0.0
            p1=np.asarray(r1.predict(X1)); p0=np.asarray(r1.predict(X0))
            A1=X1.reindex(columns=X2.columns,fill_value=0)
            A0=X0.reindex(columns=X2.columns,fill_value=0)
            m1=np.exp(np.asarray(r2.predict(A1)))*smear
            m0=np.exp(np.asarray(r2.predict(A0)))*smear
            e1=float(np.average(p1*m1,weights=w)); e0=float(np.average(p0*m0,weights=w))
            a=e1-e0
            tot=TOTAL.get(db,np.nan)
            attr.append(dict(db=db,cat=cat,n=len(d),n_positive=int((d[vcol]>0).sum()),
                             attributable_2020intl=round(a,2),
                             pct_of_total_attributable=round(100*a/tot,1) if tot and not np.isnan(tot) else None,
                             smearing=round(smear,3),
                             or_any=rows[-2]['effect'] if len(rows)>=2 else None,
                             ratio_amount=rows[-1]['effect'] if r2 is not None else None))
            log(f"            归因={a:>8,.1f} 国际元/年 (占总额归因 "
                f"{100*a/tot if tot and not np.isnan(tot) else float('nan'):>6.1f}%) "
                f"OR={np.exp(r1.params['arth']):.3f} 金额比={np.exp(r2.params['arth']):.3f} "
                f"n={len(d):,}")
    log("")

# ---- 按分项汇总归因金额的会计闭合 ----
log("########## 会计闭合：五类归因金额之和 vs 总额归因金额 ##########")
A=pd.DataFrame(attr)
for db in ['mhas','share','lasi','charls']:
    s=A[(A.db==db)&(A.cat.isin(CATS))]
    if len(s)==0: continue
    tot=TOTAL.get(db,np.nan); sm=s.attributable_2020intl.sum()
    log(f"  {db:<8s} Σ五类归因={sm:>9,.1f}  总额归因={tot:>9,.1f}  "
        f"比值={sm/tot if tot and not np.isnan(tot) else float('nan'):.3f} "
        f"(分项覆盖 {', '.join(s.cat.tolist())})")
log("  注：差额来自各分项独立建模的 smearing / 非线性，属模型近似，非数据不一致。")

# ---- 随机效应合并（仅主库可得数 >=3 的相对效应） ----
R=pd.DataFrame(rows); metas=[]
for oc in sorted(R.outcome.unique()):
    q=R[(R.outcome==oc)&(R.db.isin(MAIN))]
    if len(q)>=3:
        m=meta_dl(q.to_dict('records')); m.update(outcome=oc,cat=oc.split('_',1)[1]); metas.append(m)
        log(f"  META {oc:<24s} k={m['k']} 合并={m['pooled_effect']:.3f} "
            f"({m['lo']:.3f}-{m['hi']:.3f}) I2={m['I2']:.1f}%")
    else:
        log(f"  META {oc:<24s} SKIP（主库可得 k={len(q)}<3，不合并，按库报告）")

R.to_csv(os.path.join(OUT,'24_a2_component_results.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')
A.to_csv(os.path.join(OUT,'24_a2_attributable.csv'),index=False,encoding='utf-8-sig',float_format='%.3f')
pd.DataFrame(shares).to_csv(os.path.join(OUT,'24_a2_shares.csv'),index=False,encoding='utf-8-sig',float_format='%.3f')
pd.DataFrame(metas).to_csv(os.path.join(OUT,'24_a2_meta.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')
fc=pd.DataFrame([dict(db=r['db'],cat=r['cat'],outcome=r['outcome'],effect=r['effect'],
                      lo=r['lo'],hi=r['hi'],n=r['n']) for r in rows]+
                [dict(db='POOLED (RE)',cat=m['cat'],outcome=m['outcome'],
                      effect=m['pooled_effect'],lo=m['lo'],hi=m['hi'],n=None) for m in metas])
fc.to_csv(os.path.join(OUT,'24_a2_forest.csv'),index=False,encoding='utf-8-sig',float_format='%.4f')
log(f"\nDONE: {len(rows)} 条分项效应、{len(attr)} 条归因金额、{len(shares)} 条份额、{len(metas)} 条 meta")
