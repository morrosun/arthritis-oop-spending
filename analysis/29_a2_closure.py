# -*- coding: utf-8 -*-
"""A2 补充：把独立 g-comp 的分项归因做会计闭合分摊，并整理 A2 主表。
独立分项模型各自 smearing / 子样本不同 -> Σ分项归因 ≠ 总额归因（实测 0.81–1.11）。
这里保留独立估计作为「分项效应证据」，另按分项构成比把 A1 总额归因强制分摊，
使 Σ = 总额（100% 闭合）；两者并列报告，不静默替换。
输出：29_a2_closure.csv / .txt / 29_a2_main_table.csv
"""
import os, time, pandas as pd, numpy as np
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CATS = ['drug','outpatient','inpatient','dental','other']
A = pd.read_csv(os.path.join(OUT,'24_a2_attributable.csv'))
G = pd.read_csv(os.path.join(OUT,'22_1a_gcomp.csv'))
S = pd.read_csv(os.path.join(OUT,'24_a2_shares.csv'))
R = pd.read_csv(os.path.join(OUT,'24_a2_component_results.csv'))
TOTAL = {r.db: r.attributable_oop_2020intl for r in G.itertuples()}
lines=[]
def log(s=''):
    print(s, flush=True); lines.append(str(s))

log("A2 会计闭合分摊｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("独立分项 g-comp 与总额 g-comp 的闭合比不等于 1（模型近似，非数据不一致）。")
log("closed = (分项独立归因 / Σ五类独立归因) × A1 总额归因；folk 是 other 的子类，不重复计入。\n")

rows=[]
for db in ['mhas','share','lasi','charls']:
    a=A[(A.db==db)&(A.cat.isin(CATS))].copy()
    if len(a)==0: continue
    s=float(a.attributable_2020intl.sum()); tot=TOTAL.get(db,None)
    for r in a.itertuples():
        pct=float(r.attributable_2020intl)/s if s else np.nan
        closed=pct*tot if tot else np.nan
        rows.append(dict(db=db,cat=r.cat,attributable_independent=r.attributable_2020intl,
                         pct_of_sum_attributable=round(100*pct,1),
                         attributable_closed=round(closed,2) if tot else None,
                         total_attributable_A1=tot,
                         closure_ratio=round(s/tot,3) if tot else None,
                         note=('extension: no A1 g-comp total' if tot is None else '')))
    log(f"  {db:<8s} Σ独立={s:>8,.1f}  总额A1={tot if tot else float('nan'):>8,.1f}  "
        f"闭合比={s/tot if tot else float('nan'):.3f}  已按构成比分摊为 Σ={tot if tot else float('nan'):,.1f}")
C=pd.DataFrame(rows)
C.to_csv(os.path.join(OUT,'29_a2_closure.csv'),index=False,encoding='utf-8-sig',float_format='%.3f')

# A2 主表：逐库逐类的 OR / 金额比 / 份额差 / 归因构成比
main=[]
for db in ['mhas','share','lasi','charls']:
    for cat in CATS+['folk']:
        o=R[(R.db==db)&(R.outcome=='any_'+cat)]
        m=R[(R.db==db)&(R.outcome=='amount_'+cat)]
        sh=S[(S.db==db)&(S.cat==cat)]
        cl=C[(C.db==db)&(C.cat==cat)]
        at=A[(A.db==db)&(A.cat==cat)]
        if len(o)==0 and len(sh)==0: continue
        main.append(dict(db=db,cat=cat,
            or_any=round(float(o.effect.iloc[0]),3) if len(o) else None,
            or_lo=round(float(o.lo.iloc[0]),3) if len(o) else None,
            or_hi=round(float(o.hi.iloc[0]),3) if len(o) else None,
            ratio_amount=round(float(m.effect.iloc[0]),3) if len(m) else None,
            ratio_lo=round(float(m.lo.iloc[0]),3) if len(m) else None,
            ratio_hi=round(float(m.hi.iloc[0]),3) if len(m) else None,
            share_diff_pp=round(float(sh.diff_pp.iloc[0]),2) if len(sh) else None,
            share_diff_p=round(float(sh.p.iloc[0]),4) if len(sh) else None,
            attributable_independent=round(float(at.attributable_2020intl.iloc[0]),1) if len(at) else None,
            pct_of_sum=round(float(cl.pct_of_sum_attributable.iloc[0]),1) if len(cl) else None,
            attributable_closed=round(float(cl.attributable_closed.iloc[0]),1)
                if len(cl) and pd.notna(cl.attributable_closed.iloc[0]) else None))
M=pd.DataFrame(main)
M.to_csv(os.path.join(OUT,'29_a2_main_table.csv'),index=False,encoding='utf-8-sig',float_format='%.3f')
log(f"\nDONE: 闭合表 {len(C)} 行、A2 主表 {len(M)} 行")
with open(os.path.join(OUT,'29_a2_closure.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines)+'\n')
