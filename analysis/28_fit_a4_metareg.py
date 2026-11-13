# -*- coding: utf-8 -*-
"""方向 A / A4：20 国制度梯度 meta 回归。
效应量：20_a1_share_by_country.csv（SHARE 逐国校正后 log OR / log 金额比 + SE，k=20）。
制度变量：27_country_context_wide.csv（World Bank WDI，2004–2015 均值 / 2004 基线，20 国内 z-score）。
主解释变量（预先指定）：oop_pct_che_z 自付占卫生总费用 %。
方法：DL 随机效应权重 W=1/(se²+τ²) 的加权最小二乘 + Knapp-Hartung 校正（t, df=k-p）；
      残差异质性用含协变量的矩估计 τ²_res，R²=(τ²_0-τ²_res)/τ²_0。
      探索性协变量做 BH-FDR；主变量做留一法与 4 组敏感性。
生态学关联，不得作因果或个体层推断。
输出：28_a4_country_data.csv / 28_a4_metareg.csv / 28_a4_leaveone.csv /
      28_a4_scatter.csv / 28_a4_summary.txt
"""
import os, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '28_a4_summary.txt')
VARS = ['oop_pct_che','uhc_index','che_pct_gdp','che_pc_usd','govt_pct_che',
        'gdp_pc_ppp','pop65_pct','gini','phys_per_1000']
PRIMARY='oop_pct_che'
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT,'w',encoding='utf-8') as f: f.write('\n'.join(lines))

def tau2_dl(y,se):
    w=1/se**2; k=len(y); mf=(w*y).sum()/w.sum()
    Q=float((w*(y-mf)**2).sum()); C=w.sum()-(w**2).sum()/w.sum()
    return max(0.,(Q-(k-1))/C) if C>0 else 0., Q, max(0.,(Q-(k-1))/Q*100) if Q>0 else 0.

def tau2_resid(y,se,z):
    """含协变量的残差异质性矩估计（固定权重 1/se²）。"""
    k=len(y); p=2
    W=1/se**2; X=sm.add_constant(np.asarray(z,float))
    A=X.T@(W[:,None]*X)
    try: b=np.linalg.solve(A,X.T@(W*y))
    except np.linalg.LinAlgError: return None,None,None
    e=y-X@b; QE=float((W*e**2).sum())
    try: C=W.sum()-np.trace(np.linalg.solve(A,X.T@((W**2)[:,None]*X)))
    except np.linalg.LinAlgError: return None,None,None
    t2=max(0.,(QE-(k-p))/C) if C>0 else 0.
    I2=max(0.,(QE-(k-p))/QE*100) if QE>0 else 0.
    return t2,I2,QE

def metareg(y,se,z,tau2=None,kh=True):
    k=len(y)
    if tau2 is None: tau2,_,_=tau2_dl(y,se)
    W=1/(se**2+tau2)
    X=sm.add_constant(np.asarray(z,float))
    r=sm.WLS(y,X,weights=W).fit()
    par=np.asarray(r.params).ravel(); bse0=np.asarray(r.bse).ravel()
    resid=y-X@par
    q=float((W*resid**2).sum()); p=X.shape[1]
    if kh:
        scale=max(1.,np.sqrt(q/(k-p)))
        se_adj=bse0*scale
        tv=par/se_adj
        pv=2*stats.t.sf(np.abs(tv),df=k-p)
        crit=stats.t.ppf(.975,k-p)
    else:
        se_adj=bse0; tv=par/se_adj
        pv=2*stats.norm.sf(np.abs(tv)); crit=1.96
    b,bs=float(par[1]),float(se_adj[1])
    return dict(beta=b,se=bs,ratio_per_sd=float(np.exp(b)),
                lo=float(np.exp(b-crit*bs)),hi=float(np.exp(b+crit*bs)),
                p=float(pv[1]),intercept=float(par[0]),k=k,tau2_used=tau2,
                kh_scale=float(max(1.,np.sqrt(q/(k-p)))))

log("方向 A / A4：20 国制度梯度 meta 回归｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("效应量 = SHARE 逐国校正后关节炎→自付的 log OR（20 国），制度变量 = WDI 2004–2015 均值 z-score。")
log("⚠️ 国家层生态学关联；不得写成因果或个体层效应。k=20，多重检验做 BH-FDR。\n")

E=pd.read_csv(os.path.join(OUT,'20_a1_share_by_country.csv'))
W=pd.read_csv(os.path.join(OUT,'27_country_context_wide.csv'))
D=E.merge(W,on='iso3',how='left')
D['log_or']=np.log(D['or_any_oop']); D['se_logor']=D['se_or']
D['log_ratio']=np.log(D['ratio_amount']); D['se_logratio']=D['se_ratio']
# 基线值也做 z-score（敏感性用）
for v in VARS:
    col=v+'_2004'
    if col in D and D[col].notna().sum()>=10:
        D[v+'_z2004']=(D[col]-D[col].mean())/D[col].std(ddof=1)
D.to_csv(os.path.join(OUT,'28_a4_country_data.csv'),index=False,encoding='utf-8-sig',float_format='%.4f')
log(f"合并完成：{len(D)} 国；or_any_oop 范围 {D.or_any_oop.min():.3f}–{D.or_any_oop.max():.3f}")
for v in VARS:
    col=v+'_z'
    log(f"  {v:<16s} z 可得 {D[col].notna().sum() if col in D else 0:>2d}/20")
y=D['log_or'].values; se=D['se_logor'].values
t20,Q0,I20=tau2_dl(y,se)
log(f"\n基线异质性：τ²={t20:.5f} Q={Q0:.2f} I²={I20:.1f}%（k=20）")
log(f"主解释变量 {PRIMARY}_z（自付占卫生总费用 %）范围 "
    f"{D[PRIMARY+'_mean0405'].min():.2f}–{D[PRIMARY+'_mean0405'].max():.2f}\n")

res=[]
def run(tag,outcome,yv,sev,cov,zcol,subset=None,kh=True,tau2=None):
    m=np.ones(len(D),bool) if subset is None else subset.values
    yy=yv[m]; ss=sev[m]; zz=D.loc[m,zcol].values
    ok=np.isfinite(yy)&np.isfinite(ss)&np.isfinite(zz)
    yy,ss,zz=yy[ok],ss[ok],zz[ok]
    if len(yy)<10: return
    r=metareg(yy,ss,zz,tau2=tau2,kh=kh)
    tr,I2r,_=tau2_resid(yy,ss,zz)
    t0,_,_=tau2_dl(yy,ss)
    R2=max(0.,(t0-tr)/t0) if (tr is not None and t0>0) else None
    res.append(dict(set=tag,outcome=outcome,covariate=cov,**r,
                    tau2_resid=tr,I2_resid=I2r,R2=R2,
                    n=int(ok.sum())))

Y={'or_any_oop':(D.log_or.values,D.se_logor.values),
   'amount_ratio':(D.log_ratio.values,D.se_logratio.values)}
# 主分析：单变量（每个制度变量单独）
for oc,(yv,sev) in Y.items():
    for v in VARS:
        zc=v+'_z'
        if zc in D: run('main_univariable',oc,yv,sev,v,zc)
# 敏感性
zp=PRIMARY+'_z'
run('sens_baseline2004','or_any_oop',*Y['or_any_oop'],PRIMARY,PRIMARY+'_z2004')
run('sens_fixed_effect','or_any_oop',*Y['or_any_oop'],PRIMARY,zp,tau2=0.0,kh=False)
run('sens_no_KH','or_any_oop',*Y['or_any_oop'],PRIMARY,zp,kh=False)
run('sens_drop_IRL','or_any_oop',*Y['or_any_oop'],PRIMARY,zp,
    subset=(D.iso3!='IRL'))
run('sens_amount_ratio','amount_ratio',*Y['amount_ratio'],PRIMARY,zp)
# 多变量探索（k=20，最多 2 协变量）
def multivar(tag,covs):
    cols=[c+'_z' for c in covs]
    m=D[cols].notna().all(axis=1)
    yy=y[m.values]; ss=se[m.values]; Z=D.loc[m.values,cols].values
    w=1/(ss**2+t20); X=sm.add_constant(Z)
    r=sm.WLS(yy,X,weights=w).fit()
    par=np.asarray(r.params).ravel(); bse0=np.asarray(r.bse).ravel()
    q=float((w*(yy-X@par)**2).sum()); p=X.shape[1]; k=len(yy)
    scale=max(1.,np.sqrt(q/(k-p))); sea=bse0*scale
    pv=2*stats.t.sf(np.abs(par/sea),df=k-p)
    crit=stats.t.ppf(.975,k-p)
    for j,c in enumerate(covs,start=1):
        b=float(par[j]); bs=float(sea[j])
        res.append(dict(set=tag,outcome='or_any_oop',covariate=c,beta=b,se=bs,
                        ratio_per_sd=float(np.exp(b)),lo=float(np.exp(b-crit*bs)),
                        hi=float(np.exp(b+crit*bs)),p=float(pv[j]),
                        intercept=float(r.params[0]),k=k,tau2_used=t20,
                        kh_scale=scale,tau2_resid=None,I2_resid=None,R2=None,n=k))
multivar('exploratory_multivariable',[PRIMARY,'gdp_pc_ppp'])
multivar('exploratory_multivariable',[PRIMARY,'govt_pct_che'])

R=pd.DataFrame(res)
# BH-FDR（仅 main_univariable 的探索性变量，主变量预先指定不参与校正）
m=R[(R.set=='main_univariable')&(R.outcome=='or_any_oop')&(R.covariate!=PRIMARY)].copy()
if len(m):
    pv=m.p.values; order=np.argsort(pv); ranked=pv[order]
    q=ranked*len(ranked)/(np.arange(len(ranked))+1)
    q=np.minimum.accumulate(q[::-1])[::-1]
    qq=np.empty(len(ranked)); qq[order]=np.minimum(q,1)
    R.loc[m.index,'q_bh']=qq
R.to_csv(os.path.join(OUT,'28_a4_metareg.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')

log("########## 单变量 meta 回归（结局 = 有无自付 OR，每 1 SD 制度变量的 OR 比） ##########")
for r in R[(R.set=='main_univariable')&(R.outcome=='or_any_oop')].itertuples():
    flag=' [主变量]' if r.covariate==PRIMARY else ''
    log(f"  {r.covariate:<16s} {r.ratio_per_sd:.3f} ({r.lo:.3f}-{r.hi:.3f}) "
        f"p={r.p:.4f} q={getattr(r,'q_bh',float('nan'))} "
        f"τ²_res={r.tau2_resid:.5f} I²_res={r.I2_resid:.1f}% R²={r.R2 if r.R2 is not None else float('nan'):.2f}{flag}")

# 留一法（主变量）
lo=[]
for iso in D.iso3:
    m=(D.iso3!=iso)
    yy=y[m.values]; ss=se[m.values]; zz=D.loc[m.values,zp].values
    rr=metareg(yy,ss,zz,tau2=t20)
    lo.append(dict(excluded=iso,beta=rr['beta'],ratio_per_sd=rr['ratio_per_sd'],
                   lo=rr['lo'],hi=rr['hi'],p=rr['p'],k=rr['k']))
LO=pd.DataFrame(lo)
LO.to_csv(os.path.join(OUT,'28_a4_leaveone.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')
log(f"\n########## 留一法（主变量） ##########")
log(f"  OR 比范围 {LO.ratio_per_sd.min():.3f}–{LO.ratio_per_sd.max():.3f}；"
    f"p<0.05 的剔除方案 {(LO.p<0.05).sum()}/{len(LO)} 个；"
    f"最敏感剔除国 = {LO.loc[LO.ratio_per_sd.idxmin(),'excluded']} / {LO.loc[LO.ratio_per_sd.idxmax(),'excluded']}")

# 散点图数据
SC=D[['iso3','or_any_oop','se_or','n','oop_pct_che_mean0405','oop_pct_che_z',
      'ratio_amount','se_ratio','gdp_pc_ppp_mean0405','govt_pct_che_mean0405']].copy()
SC['log_or']=np.log(SC.or_any_oop); SC['invvar']=1/SC.se_or**2
SC.to_csv(os.path.join(OUT,'28_a4_scatter.csv'),index=False,encoding='utf-8-sig',float_format='%.4f')
log("\n########## 敏感性（主变量） ##########")
for r in R[R.set.str.startswith('sens')|R.set.str.startswith('exploratory')].itertuples():
    log(f"  {r.set:<28s} {r.covariate:<14s} {r.outcome:<14s} "
        f"{r.ratio_per_sd:.3f} ({r.lo:.3f}-{r.hi:.3f}) p={r.p:.4f} k={r.k}")
log("\n⚠️ 解释边界：国家层生态关联，制度变量彼此高度相关（如 OOP% 与政府占比近似互补），"
    "单变量结果不可作因果解释；多变量仅作探索，k=20 不支持更多协变量。")
log(f"\nDONE: {len(R)} 条 meta 回归、{len(LO)} 条留一法")
