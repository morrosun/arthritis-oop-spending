# -*- coding: utf-8 -*-
"""A1 遗留诊断①：MHAS 2003→2012 九年断档。

背景：MHAS 波次年份 2001/2003/2012/2015/2018/2021，w2→w3 间隔 9 年，
      其余约 3 年。A3 的 yrs6 敏感性已显示 MHAS 发病后平均效应减弱到
      0.1136 (p=0.208)。本脚本检验 A1 主结局是否也由 w1/w2 驱动。
设计：
  set=all6      : 主分析原样（MHAS w1–w6）
  set=w3w6      : MHAS 仅 w3–w6（去掉断档前的两波），其余库不变
  set=w1w2      : MHAS 仅 w1–w2（仅作描述，不进 meta）
  另给 MHAS 逐波 P1 / P2inc 效应，定位断档前后差异。
复用 21_fit_a1_revised.py 的函数定义（只 exec 函数定义段，不执行其主流程）。
输出：30_diag_mhas_w3w6.csv / 30_diag_mhas_w3w6.txt / 30_diag_mhas_w3w6_meta.csv
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
# head 内定义的 log 会写 21_a1_results.txt；此处改指向本诊断文件，避免污染原结果
TXT = os.path.join(OUT, '30_diag_mhas_w3w6.txt')
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

MAIN = ['mhas', 'hrs', 'share', 'lasi']
DATA = {db: pd.read_csv(os.path.join(OUT, f'18_data_{db}.csv'), low_memory=False)
        for db in MAIN}

log("A1 遗留诊断①：MHAS 2003→2012 九年断档｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("口径：加权 + 完整协变量 + 个体 ID 聚类稳健 SE；B10/B40 的 SHARE 仅 w1；按库 DL 随机效应合并。")
log("MHAS 波次年份：w1 2001 / w2 2003 / w3 2012 / w4 2015 / w5 2018 / w6 2021（w2→w3 间隔 9 年）\n")

ALL, METAS = [], []
SETS = [
    ('all6',  None,      '主分析原样：MHAS w1–w6'),
    ('w3w6',  [3,4,5,6], 'MHAS 仅 w3–w6（剔除断档前两波）'),
    ('w1w2',  [1,2],     'MHAS 仅 w1–w2（仅描述，不进主 meta 对照）'),
]
for tag, waves, note in SETS:
    log(f"\n########## {tag} ########## {note}")
    for db in MAIN:
        d = DATA[db]
        if db == 'mhas' and waves is not None:
            d = d[d.wave.isin(waves)]
        try:
            r = one(db, tag, d, burden_mode='exclude_share_w2plus')
            ALL.extend(r)
            log(f"  {db:<6s} n={r[0]['n']:,} " + ' | '.join(
                f"{x['outcome'].split('_')[0]}={x['effect']:.3f}({x['lo']:.3f}-{x['hi']:.3f})"
                for x in r))
        except Exception as e:
            log(f"  {db}: 失败 {type(e).__name__} {str(e)[:160]}")

# 三个主 set 各自独立合并（w1w2 也合并仅供对照，不代表可用样本）
for tag in ['all6', 'w3w6', 'w1w2']:
    for oc in ['P1_any_oop', 'P2_amount_log', 'P2inc_amount_log_adj_income',
               'B10_oop_ge10pct_income', 'B40_oop_ge40pct_income']:
        rows = [x for x in ALL if x['set'] == tag and x['outcome'] == oc and x['db'] in MAIN]
        if len(rows) >= 2:
            m = meta_dl(rows); m.update(set=tag, outcome=oc); METAS.append(m)

# MHAS 逐波效应（P1 + P2inc），定位断档前后
log("\n########## MHAS 逐波效应 ##########")
WAVER = []
for w in [1,2,3,4,5,6]:
    d = DATA['mhas']; d = d[d.wave == w]
    try:
        r = one('mhas', f'mhas_w{w}', d, burden_mode='exclude_share_w2plus',
                outcomes=('P1','P2','P2inc'))
        for x in r:
            x['wave'] = w; WAVER.append(x)
        log(f"  w{w} (n={r[0]['n']:,}): " + ' | '.join(
            f"{x['outcome'].split('_')[0]}={x['effect']:.3f}({x['lo']:.3f}-{x['hi']:.3f})"
            for x in r))
    except Exception as e:
        log(f"  w{w}: 失败 {type(e).__name__} {str(e)[:140]}")

log("\n########## 合并效应对照 ##########")
for tag in ['all6', 'w3w6']:
    for oc in ['P1_any_oop', 'P2inc_amount_log_adj_income', 'B40_oop_ge40pct_income']:
        m = [x for x in METAS if x['set']==tag and x['outcome']==oc]
        if m:
            m = m[0]
            log(f"  {tag:<6s} {oc:<32s} {m['pooled_effect']:.4f} "
                f"({m['lo']:.4f}-{m['hi']:.4f}) I2={m['I2']:.1f}% k={m['k']}")

with open(os.path.join(OUT,'30_diag_mhas_w3w6.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(ALL).to_csv(f, index=False, float_format='%.6f')
with open(os.path.join(OUT,'30_diag_mhas_w3w6_meta.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(METAS).to_csv(f, index=False, float_format='%.6f')
with open(os.path.join(OUT,'30_diag_mhas_wave.csv'),'w',encoding='utf-8-sig',newline='') as f:
    pd.DataFrame(WAVER).to_csv(f, index=False, float_format='%.6f')
log(f"\nDONE: {len(ALL)} 条估计 / {len(METAS)} 条 meta / {len(WAVER)} 条逐波")
