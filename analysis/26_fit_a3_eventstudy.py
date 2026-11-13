# -*- coding: utf-8 -*-
"""方向 A / A3：新发关节炎 event study（个体固定效应 + 波次固定效应）。
数据：25_event_<db>.csv（从原始库抽全量 arthre 序列，0->1 定义新发；对照 = never-diagnosed）。
模型：within 变换（按 id 去均值）后 OLS，SE 按个体 ID 聚类稳健；
      y = Σ_k β_k·1[event_time=k] + 波次 FE (+可选时变协变量)，参考期 event_time=-1。
结局：① 有无自付（线性概率）② log(1+年化自付 2020国际元) ③ 有支出者 log 金额。
检验：前置趋势 β_-3/β_-2 联合 Wald；发病后 β_0..β_3 平均效应。
按库分别估计，**不做 naïve pooling**；CHARLS 因累计性违规 + 金额可得率低，仅作附注。
输出：26_a3_eventstudy.csv / 26_a3_summary.txt / 26_a3_tests.csv / 26_a3_flow.csv
"""
import os, time, warnings, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '26_a3_summary.txt')
KS = [-3,-2,0,1,2,3]           # -1 为参考期
OUTCOMES = [('pos','any_oop_LPM'),('log1p_oop','log1p_amount'),('log_oop_pos','log_amount_positive')]
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT,'w',encoding='utf-8') as f: f.write('\n'.join(lines))
def kname(k): return 'ev_'+('m'+str(-k) if k<0 else str(k))

log("方向 A / A3：新发关节炎 event study｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("暴露：r{w}arthre ever-diagnosed 累计标记，0->1 一次性转换定义新发；")
log("      排除基线现患（左删失）与累计性违规者；对照 = 所有波均 arth=0 且 >=3 波者。")
log("参考期 event_time=-1；窗口 [-3,+3]（以观测序号计，另报告年份跨度）。")
log("个体 FE + 波次 FE，within 变换后 OLS，SE 聚类到个体 ID；线性概率系数另换算为百分点。\n")

DATA={}
for db in ['mhas','hrs','share','charls']:
    p=os.path.join(OUT,f'25_event_{db}.csv')
    if os.path.exists(p): DATA[db]=pd.read_csv(p,low_memory=False,dtype={'id':str})

def prepare(d, set_):
    x=d.copy()
    if set_=='noimp': x=x[x['imputed'].fillna(0)==0]
    if set_=='yrs6':
        lim=x['years_from_onset'].abs()<=6
        x=x[lim | (x.group=='never')]
    return x

def one(db,set_,ycol,yname,x):
    d=x[((x.group=='onset')&x.event_time.between(-3,3))|(x.group=='never')].copy()
    d=d[d[ycol].notna()].reset_index(drop=True)
    if len(d)<500: return [],[]
    # 事件虚拟变量（never 组全 0）
    for k in KS: d[kname(k)]=((d.group=='onset')&(d.event_time==k)).astype(float)
    wv=pd.get_dummies(d['wave'].astype('Int64').astype(str),prefix='wv',drop_first=True)
    d=pd.concat([d,wv],axis=1)
    cols=[ycol]+[kname(k) for k in KS]+list(wv.columns)
    if set_=='adj':
        for c in ['age','shlt','adl_any','married']:
            if c in d and d[c].notna().mean()>0.9: cols.append(c)
        d=d.dropna(subset=cols).reset_index(drop=True)
        if len(d)<500: return [],[]
        wv=wv.loc[d.index]
    if set_=='nowaveFE':
        cols=[ycol]+[kname(k) for k in KS]
    X=d[cols].copy()
    if set_=='adj':
        X['age']=(X['age']-70)/10.0
    # within 变换
    dm=X.groupby(d['id']).transform('mean')
    Xw=X-dm
    yw=Xw.pop(ycol)
    Xw=Xw.loc[:,Xw.std()>1e-12]
    if Xw.shape[1]<len(KS)-1: return [],[]
    try:
        r=sm.OLS(yw,Xw).fit(cov_type='cluster',cov_kwds={'groups':d['id']})
    except Exception:
        r=sm.OLS(yw,Xw).fit(cov_type='HC0')
    rows=[]
    for k in KS:
        col=kname(k)
        if col not in r.params.index: continue
        b=float(r.params[col]); se=float(r.bse[col])
        yr=d.loc[(d.group=='onset')&(d.event_time==k),'years_from_onset']
        rows.append(dict(set=set_,db=db,outcome=yname,k=k,beta=b,se=se,
                         lo=b-1.96*se,hi=b+1.96*se,
                         beta_pp=100*b,lo_pp=100*(b-1.96*se),hi_pp=100*(b+1.96*se),
                         unit=('percentage_points' if yname=='any_oop_LPM' else '100x_log_units'),
                         role=('extension' if db=='charls' else 'main'),
                         p=float(2*stats.norm.sf(abs(b/se))),
                         n=len(d),n_ids=int(d.id.nunique()),
                         n_onset_rows=int(((d.group=='onset')&(d.event_time==k)).sum()),
                         years_from_onset_median=float(yr.median()) if len(yr) else None))
    # 前置趋势联合 Wald
    tests=[]
    pre=[kname(k) for k in KS if k<0 and kname(k) in r.params.index]
    if len(pre)>=2:
        R=np.zeros((len(pre),len(r.params)))
        for i,c in enumerate(pre): R[i,list(r.params.index).index(c)]=1
        try:
            ft=r.f_test(R)
            tests.append(dict(set=set_,db=db,outcome=yname,test='pretrend_joint',
                              stat=float(np.ravel(ft.statistic)[0]),
                              p=float(np.ravel(ft.pvalue)[0]),df1=len(pre),
                              n=len(d),n_ids=int(d.id.nunique())))
        except Exception as e:
            tests.append(dict(set=set_,db=db,outcome=yname,test='pretrend_joint',
                              stat=None,p=None,df1=len(pre),n=len(d),
                              n_ids=int(d.id.nunique())))
    post=[kname(k) for k in KS if k>=0 and kname(k) in r.params.index]
    if len(post)>=2:
        L=np.zeros(len(r.params))
        for c in post: L[list(r.params.index).index(c)]=1.0/len(post)
        try:
            tt=r.t_test(L)
            tests.append(dict(set=set_,db=db,outcome=yname,test='post_onset_average',
                              stat=float(np.ravel(tt.effect)[0]),
                              p=float(np.ravel(tt.pvalue)[0]),df1=len(post),
                              n=len(d),n_ids=int(d.id.nunique())))
        except Exception: pass
    return rows,tests

SETS=['main','adj','noimp','nowaveFE','yrs6']
allrows,alltests,flow=[],[],[]
for db in ['mhas','hrs','share','charls']:
    if db not in DATA: continue
    sets=['main'] if db=='charls' else SETS
    log(f"########## {db} ##########")
    for set_ in sets:
        x=prepare(DATA[db],set_)
        for ycol,yname in OUTCOMES:
            t0=time.time()
            rr,tt=one(db,set_,ycol,yname,x)
            allrows.extend(rr); alltests.extend(tt)
            if set_=='main':
                n_ids=rr[0]['n_ids'] if rr else 0
                log(f"  {yname:<20s} n={rr[0]['n']:,} ids={n_ids:,} "
                    + ' '.join(f"k{r['k']:+d}:{r['beta_pp']:+.2f}pp" for r in rr if r['k'] in (-2,0,1,2))
                    + f" [{time.time()-t0:.1f}s]")
                flow.append(dict(db=db,outcome=yname,n=rr[0]['n'] if rr else 0,
                                 n_ids=n_ids,set=set_))
    # 主设定前置趋势与发病后平均
    for t in alltests:
        if t['db']==db and t['set']=='main':
            log(f"    {t['outcome']:<20s} {t['test']:<20s} stat={t['stat']} p={t['p']}")
    log("")

R=pd.DataFrame(allrows); T=pd.DataFrame(alltests)
R.to_csv(os.path.join(OUT,'26_a3_eventstudy.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')
T.to_csv(os.path.join(OUT,'26_a3_tests.csv'),index=False,encoding='utf-8-sig',float_format='%.6f')
pd.DataFrame(flow).to_csv(os.path.join(OUT,'26_a3_flow.csv'),index=False,encoding='utf-8-sig')
log("########## 前置趋势判定（main，α=0.05） ##########")
for t in T[(T.set=='main')&(T.test=='pretrend_joint')].itertuples():
    if t.p is None: continue
    log(f"  {t.db:<7s} {t.outcome:<20s} p={float(t.p):.4f} -> "
        + ('前置趋势存在，谨慎解读' if float(t.p)<0.05 else '未见显著前置趋势'))
log(f"\nDONE: {len(R)} 条 event-time 系数、{len(T)} 条联合检验")
