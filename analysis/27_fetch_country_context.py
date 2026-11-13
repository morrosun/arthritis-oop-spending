# -*- coding: utf-8 -*-
"""方向 A / A4 数据层：抓取 SHARE 20 国的制度/宏观协变量（World Bank WDI API）。
主解释变量（预先指定）：SH.XPD.OOPC.CH.ZS 自付占卫生总费用 %。
其余为探索性协变量；每个指标记录 lastupdated、缺失年数。
口径：主分析用 2004–2015 均值（覆盖 SHARE w1/2/5/6 的调查年份），
      敏感性用 2004 基线值；meta 回归按 20 国 z-score 解释「每 1 SD」。
输出：27_country_context.csv / 27_country_context_wide.csv /
      27_fetch_country_context.txt / 27_wb_<ind>.json
"""
import os, json, time, urllib.request, ssl, pandas as pd, numpy as np
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '27_fetch_country_context.txt')
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
URL = ("https://api.worldbank.org/v2/country/all/indicator/{ind}"
       "?format=json&date=2000:2018&per_page=20000")
IND = {
 'SH.XPD.OOPC.CH.ZS': 'oop_pct_che',
 'SH_UHC_SCI':        'uhc_index',   # 旧 ID SH.UHC.SRVS.CV.XD 已归档，改用 WDI 现行 ID
 'SH.XPD.CHEX.GD.ZS': 'che_pct_gdp',
 'SH.XPD.CHEX.PC.CD': 'che_pc_usd',
 'SH.XPD.GHED.CH.ZS': 'govt_pct_che',
 'NY.GDP.PCAP.PP.KD': 'gdp_pc_ppp',
 'SP.POP.65UP.TO.ZS': 'pop65_pct',
 'SI.POV.GINI':       'gini',
 'SH.MED.PHYS.ZS':    'phys_per_1000',
}
ISOS = ['AUT','BEL','CHE','CZE','DEU','DNK','ESP','EST','FRA','GRC',
        'HRV','IRL','ISR','ITA','LUX','NLD','POL','PRT','SVN','SWE']
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT,'w',encoding='utf-8') as f: f.write('\n'.join(lines))
def fetch(ind, tries=4, timeout=90):
    last=''
    for k in range(tries):
        try:
            req=urllib.request.Request(URL.format(ind=ind),headers={'User-Agent':'Mozilla/5.0'})
            r=urllib.request.urlopen(req,timeout=timeout,context=CTX)
            o=json.loads(r.read().decode('utf-8'))
            if not isinstance(o,list) or len(o)<2 or o[1] is None:
                last=f'bad payload {str(o)[:120]}'
            else:
                out={}
                for d in o[1]:
                    iso=d.get('countryiso3code')
                    if iso in ISOS:
                        out.setdefault(iso,{})[int(d['date'])]=d['value']
                return o[0].get('lastupdated'),out,None
        except Exception as e:
            last=f'{type(e).__name__}: {str(e)[:120]}'
        time.sleep(2)
    return None,None,last

log("方向 A / A4 数据层：World Bank WDI 国家制度变量抓取｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log(f"目标国家 {len(ISOS)} 个；年份 2000–2018；主窗口 2004–2015\n")
raw={}; longrows=[]
for ind,short in IND.items():
    t0=time.time(); lu,d,err=fetch(ind)
    if d is None:
        log(f"  {ind:<22s} FAIL {err}"); continue
    raw[short]=dict(indicator=ind,lastupdated=lu,data=d)
    with open(os.path.join(OUT,'27_wb_'+short+'.json'),'w',encoding='utf-8') as f:
        json.dump(dict(indicator=ind,lastupdated=lu,data=d),f,ensure_ascii=False)
    nval=sum(1 for iso in d for v in d[iso].values() if v is not None)
    log(f"  {ind:<22s} OK 国家={len(d)} 非空值={nval} lastupdated={lu} [{time.time()-t0:.1f}s]")
    for iso in sorted(d):
        for y in sorted(d[iso]):
            if d[iso][y] is not None:
                longrows.append(dict(iso3=iso,indicator=ind,name=short,year=y,value=float(d[iso][y])))
L=pd.DataFrame(longrows)
L.to_csv(os.path.join(OUT,'27_country_context.csv'),index=False,encoding='utf-8-sig',
         float_format='%.4f')

# wide：主窗口均值 / 2004 基线 / 可用年数
W=pd.DataFrame({'iso3':ISOS})
for ind,short in IND.items():
    sub=L[L.indicator==ind]
    mean=sub[(sub.year>=2004)&(sub.year<=2015)].groupby('iso3')['value'].mean()
    base=sub[sub.year==2004].set_index('iso3')['value']
    nyr=sub[(sub.year>=2004)&(sub.year<=2015)].groupby('iso3')['value'].count()
    W[short+'_mean0405']=W.iso3.map(mean)
    W[short+'_2004']=W.iso3.map(base)
    W[short+'_nyears']=W.iso3.map(nyr).fillna(0).astype(int)
# z-score（20 国内标准化，用于 meta 回归每 1 SD 的解释）
for ind,short in IND.items():
    col=short+'_mean0405'
    if col in W and W[col].notna().sum()>=10:
        W[short+'_z']=(W[col]-W[col].mean())/W[col].std(ddof=1)
W.to_csv(os.path.join(OUT,'27_country_context_wide.csv'),index=False,
         encoding='utf-8-sig',float_format='%.4f')
log("\n########## 20 国制度变量覆盖（2004–2015 均值） ##########")
for ind,short in IND.items():
    col=short+'_mean0405'
    if col not in W: continue
    s=W[col]
    log(f"  {short:<16s} 可得 {s.notna().sum():>2d}/20  "
        f"min={s.min():.2f} 中位={s.median():.2f} max={s.max():.2f}  "
        f"缺失={','.join(W.loc[s.isna(),'iso3'].tolist()) or '无'}")
log("\n主解释变量 oop_pct_che（自付占卫生总费用 %）逐国：")
for r in W[['iso3','oop_pct_che_mean0405','oop_pct_che_2004']].itertuples():
    log(f"  {r.iso3} 均值={r.oop_pct_che_mean0405:.2f}  2004={r.oop_pct_che_2004:.2f}")
log("\nDONE -> 27_country_context.csv / 27_country_context_wide.csv")
