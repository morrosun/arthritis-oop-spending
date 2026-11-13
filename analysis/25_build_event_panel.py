# -*- coding: utf-8 -*-
"""方向 A / A3 数据层：从原始库抽取**全量**关节炎累计序列，构建新发 event-study 面板。
关键：18_data 已按「金额有效 + 协变量完整」过滤，直接用会漏波 -> 误判新发。
本脚本先抽 r{w}arthre 全序列（只读，不做金额过滤），再与 18 的金额/协变量按 (wave,id) 左连接。

新发定义：按人按波排序，序列形如 0...0 1...1；首次 0->1 的波为 onset。
  * 排除左删失（首个观测即 arth=1 的现患病例）
  * 要求 >=1 个 arth=0 的前置观测、>=1 个发病时/后观测
  * 对照组 = 所有观测均 arth=0 且 >=3 波观测的 never-diagnosed 个体
event_time = 相对 onset 的**观测序号**（波间隔不等，另给 years_from_onset）
输出：25_event_<db>.csv、25_event_flow.txt / .csv
"""
import os, time, warnings, psycopg2, pandas as pd, numpy as np
from psycopg2 import sql
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '25_event_flow.txt')

CFG = {
 'mhas': dict(key='rahhidnp', waves=list(range(1,7)), prefix='h_mhas_d_p',
              years={1:2001,2:2003,3:2012,4:2015,5:2018,6:2021}),
 'hrs': dict(key='hhidpn', waves=list(range(3,17)), prefix='randhrs1992_2022v1_p',
             years={w:1992+2*(w-1) for w in range(3,17)}),
 'share': dict(key='mergeid', waves=[1,2,5,6], prefix='gh_share_p',
               years={1:2004,2:2007,5:2013,6:2015}),
 'charls': dict(key='id', waves=[1,2,3,4], prefix='harm_h_charls_d_data_p',
                years={1:2011,2:2013,3:2015,4:2018}),
}
META = ('catalog','keys','value_label','variable_label','wave_map','_vl','_hcap_',
        'covid','_eol','_lh_','gvwt','harm_map','_long')
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT,'w',encoding='utf-8') as f: f.write('\n'.join(lines))
def norm_id(s):
    s=s.astype(str).str.strip()
    return s.str.replace(r'\.0+$','',regex=True)
def c(col):
    return sql.SQL("NULLIF({}::text,'')::numeric").format(sql.Identifier(col))

log("方向 A / A3 数据层：新发关节炎事件面板构建｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("arthre = ever-diagnosed 累计标记（阳性不回落）-> 0->1 的一次性转换可定义新发。")
log("LASI 仅 1 波，无法识别新发，不进 A3；HRS 自 w3 起（与 A1 一致）。\n")

flow=[]
for db,cfg in CFG.items():
    log(f"########## {db} ########## waves={cfg['waves']}")
    conn=psycopg2.connect(CONN+' dbname='+db); cur=conn.cursor()
    cur.execute("SET statement_timeout='300s'")
    cur.execute("""SELECT table_name,column_name FROM information_schema.columns
                   WHERE table_schema='public' ORDER BY table_name,ordinal_position""")
    colmap={}
    for t,col in cur.fetchall():
        if any(m in t.lower() for m in META): continue
        colmap.setdefault(col.lower(),[]).append(t)
    def pick(name):
        cand=colmap.get(name.lower()) or []
        pref=[t for t in cand if cfg['prefix'] in t]
        return (pref or cand or [None])[0]
    seq=[]
    for w in cfg['waves']:
        av=f'r{w}arthre'; tb=pick(av)
        if not tb:
            log(f"  w{w}: 缺 {av} -> SKIP"); continue
        q=sql.SQL("SELECT {k} AS id, {c} AS arth FROM public.{t}").format(
            k=sql.Identifier(cfg['key']), c=c(av), t=sql.Identifier(tb))
        cur.execute(q)
        d=pd.DataFrame(cur.fetchall(),columns=['id','arth'])
        d['id']=norm_id(d['id']); d['wave']=w; d['year']=cfg['years'][w]
        d['arth']=pd.to_numeric(d['arth'],errors='coerce')
        seq.append(d[['id','wave','year','arth']])
        log(f"  w{w} [{tb}]: {len(d):,} 行, arth=1 {int((d.arth==1).sum()):,}, "
            f"arth=0 {int((d.arth==0).sum()):,}, 缺失 {int(d.arth.isna().sum()):,}")
    conn.close()
    S=pd.concat(seq,ignore_index=True).drop_duplicates(['id','wave'],keep='first')
    S=S[S['arth'].isin([0,1])].copy()
    S=S.sort_values(['id','wave']).reset_index(drop=True)
    S['seq']=S.groupby('id').cumcount()
    S['nobs']=S.groupby('id')['wave'].transform('size')
    S['ever1']=S.groupby('id')['arth'].transform('max')
    S['first_arth_wave']=S[S.arth==1].groupby('id')['wave'].transform('min')
    S['first_arth_wave']=S.groupby('id')['first_arth_wave'].transform('min')
    S['first_obs']=S.groupby('id')['wave'].transform('min')
    # 累计性检查：一旦为 1 之后是否出现 0
    S['future_min']=S[::-1].groupby('id')['arth'].cummin()[::-1]
    S['violate']=((S.arth==1)&(S.future_min==0)).astype(int)
    n_violate=int(S.loc[S.violate==1,'id'].nunique())
    # 新发：首观测为 0、有 1、且 1 之前至少有一个 0
    onset_ids=S[(S.arth==1)].groupby('id')['wave'].min()
    prev0=S[(S.arth==0)].groupby('id')['wave'].max()
    ok=set(onset_ids.index) & set(prev0.index)
    ok={i for i in ok if prev0[i] < onset_ids[i]}
    S['group']=np.where(S['id'].isin(ok),'onset',
                np.where(S['ever1']==0,'never','prevalent_or_other'))
    # onset 个体的 event_time
    ow=S[S.arth==1].groupby('id')['wave'].min().to_dict()
    oseq=S[S.arth==1].sort_values(['id','wave']).drop_duplicates('id').set_index('id')['seq'].to_dict()
    oyear=S[S.arth==1].sort_values(['id','wave']).drop_duplicates('id').set_index('id')['year'].to_dict()
    S['onset_wave']=S['id'].map(ow)
    S['event_time']=np.where(S.group=='onset', S['seq']-S['id'].map(oseq), np.nan)
    S['years_from_onset']=np.where(S.group=='onset', S['year']-S['id'].map(oyear), np.nan)
    # 对照组要求 >=3 波观测；排除累计性违规者
    bad=set(S.loc[S.violate==1,'id'])
    S.loc[S.id.isin(bad),'group']='violated_accumulation'
    S.loc[(S.group=='never')&(S.nobs<3),'group']='never_lt3waves'
    # 与 18 的金额/协变量合并
    B=pd.read_csv(os.path.join(OUT,f'18_data_{db}.csv'),low_memory=False,dtype={'id':str})
    B['id']=norm_id(B['id'])
    bcols=['id','wave','oop_annual_lcu','oop_2020intl','hhinc','age','female','educ',
           'married','shlt','adl_any','diabe','hibpe','stroke','rural','weight','imputed',
           'deflator_2020','iso3']
    B=B[[x for x in bcols if x in B.columns]].drop_duplicates(['id','wave'])
    M=S.merge(B,on=['id','wave'],how='left')
    M['db']=db
    M['pos']=np.where(M.oop_annual_lcu.notna(),(M.oop_annual_lcu>0).astype(float),np.nan)
    M['log1p_oop']=np.log1p(M['oop_2020intl'].clip(lower=0))
    M['log_oop_pos']=np.where(M.oop_2020intl>0,np.log(M.oop_2020intl),np.nan)
    M['has_amount']=M['oop_2020intl'].notna().astype(int)
    keep=['db','id','wave','year','seq','nobs','arth','group','event_time',
          'years_from_onset','onset_wave','pos','log1p_oop','log_oop_pos','has_amount',
          'oop_annual_lcu','oop_2020intl','hhinc','age','female','educ','married','shlt',
          'adl_any','diabe','hibpe','stroke','rural','weight','imputed','iso3']
    M=M[[x for x in keep if x in M.columns]]
    M.to_csv(os.path.join(OUT,f'25_event_{db}.csv'),index=False,encoding='utf-8-sig',
             float_format='%.6f')
    n_on=M.loc[M.group=='onset','id'].nunique(); n_nv=M.loc[M.group=='never','id'].nunique()
    on=M[M.group=='onset']
    f=dict(db=db,n_ids=int(M.id.nunique()),n_rows=len(M),
           n_onset_ids=n_on,n_never_ids=n_nv,
           n_prevalent=int(M.loc[M.group=='prevalent_or_other','id'].nunique()),
           n_violated=n_violate,
           n_never_lt3=int(M.loc[M.group=='never_lt3waves','id'].nunique()),
           onset_rows=len(on),onset_amount_coverage=round(100*on.has_amount.mean(),1) if len(on) else None,
           onset_event_time_min=float(on.event_time.min()) if len(on) else None,
           onset_event_time_max=float(on.event_time.max()) if len(on) else None,
           onset_year_gap_median=float(on.years_from_onset.median()) if len(on) else None)
    flow.append(f)
    log(f"  识别：onset {n_on:,} 人 / never {n_nv:,} 人 / 基线现患 "
        f"{f['n_prevalent']:,} 人 / 累计性违规 {n_violate:,} 人")
    log(f"  onset 组人波 {len(on):,}，金额可得 {f['onset_amount_coverage']}%，"
        f"event_time 范围 [{f['onset_event_time_min']}, {f['onset_event_time_max']}]")
    # event_time 分布
    if len(on):
        vc=on.event_time.value_counts().sort_index()
        log("  event_time 人波分布: " + ' '.join(f"{int(k):+d}:{v:,}" for k,v in vc.items()))
    log("")

pd.DataFrame(flow).to_csv(os.path.join(OUT,'25_event_flow.csv'),index=False,
                          encoding='utf-8-sig',float_format='%.2f')
log("DONE -> 25_event_<db>.csv / 25_event_flow.csv")
