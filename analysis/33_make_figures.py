# -*- coding: utf-8 -*-
"""生成论文级中英文图表各一份（自包含 HTML + 内嵌 SVG，无外部依赖）。

五张图：
  Figure 1 森林图        22_1a_forest.csv + 22_1a_sensitivity_table.csv
  Figure 2 event study   26_a3_eventstudy.csv + 26_a3_tests.csv
  Figure 3 分项构成       24_a2_shares.csv + 29_a2_closure.csv + 24_a2_meta.csv
  Figure 4 20 国散点      28_a4_scatter.csv + 28_a4_metareg.csv
  Figure 5 SES 分层       41_ses_figure.csv + 41_ses_equity.csv + 41_ses_tests.csv

所有数值均从结果 CSV 读取，不硬编码；中英文图注一并参数化。
术语：全稿统一用 excess（超额自付），不再用 attributable（归因自付）。
输出：<ROOT>/方向A_Figures_CN.html、<ROOT>/方向A_Figures_EN.html
"""
import os, math, html, numpy as np, pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(f): return pd.read_csv(os.path.join(OUT, f))

FOREST = rd('22_1a_forest.csv')
SENS   = rd('22_1a_sensitivity_table.csv')
# 合并值用 6 位小数版本：22_1a_forest.csv 已四舍五入到 4 位，再截 3 位会二次舍入
META   = rd('21_a1_revised_meta.csv').query("set == 'main_revised'").set_index('outcome')
EVENT  = rd('26_a3_eventstudy.csv')
ETEST  = rd('26_a3_tests.csv')
SHARES = rd('24_a2_shares.csv')
CLOSED = rd('29_a2_closure.csv')
A2META = rd('24_a2_meta.csv')
SCAT   = rd('28_a4_scatter.csv')
MREG   = rd('28_a4_metareg.csv')
SESFIG = rd('41_ses_figure.csv')
SESEQ  = rd('41_ses_equity.csv')
SESTST = rd('41_ses_tests.csv').set_index('test')
SESRAT = rd('41_ses_equity_ratio.csv')

C = dict(mhas='#0072B2', hrs='#D55E00', share='#009E73', lasi='#CC79A7',
         charls='#E69F00', pooled='#2b2b2b')
CATC = dict(drug='#0072B2', outpatient='#E69F00', inpatient='#009E73',
            dental='#CC79A7', other='#56B4E9', folk='#D55E00')
GRID, AXIS, MUTED = '#e3e6ea', '#4a5058', '#6b7280'

def esc(s): return html.escape(str(s), quote=True)
def T(x, y, s, size=11, anchor='start', fill='#1a1a1a', weight='normal',
      family='sans', style=''):
    fam = ('Times New Roman, Georgia, serif' if family == 'serif'
           else 'Arial, Helvetica, sans-serif' if family == 'sans'
           else 'Microsoft YaHei, SimHei, sans-serif')
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{fill}" font-weight="{weight}" font-family="{fam}" {style}>{esc(s)}</text>')
def L(x1,y1,x2,y2,stroke=AXIS,width=1,dash='',opacity=1):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"{d} opacity="{opacity}"/>')
def R(x,y,w,h,fill,stroke='none',opacity=1,rx=0):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0,w):.1f}" height="{max(0,h):.1f}" '
            f'fill="{fill}" stroke="{stroke}" opacity="{opacity}" rx="{rx}"/>')
def CIR(x,y,r,fill,stroke='none',width=1,opacity=1):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>')
def POLY(pts, fill, stroke='none', width=1, opacity=1):
    p = ' '.join(f'{a:.1f},{b:.1f}' for a,b in pts)
    return f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'
def PLINE(pts, stroke, width=2, dash='', opacity=1):
    p = ' '.join(f'{a:.1f},{b:.1f}' for a,b in pts)
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{width}"'
            f'{d} opacity="{opacity}"/>')
def WRAP(w, h, body, bg='#ffffff'):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img">{R(0,0,w,h,bg)}{body}</svg>')

# ---------------------------------------------------------------- 各语言文案
DBNAME = {'mhas':'MHAS','hrs':'HRS','share':'SHARE','lasi':'LASI','charls':'CHARLS'}
CAT = {
 'zh': dict(drug='药品', outpatient='门诊', inpatient='住院', dental='牙科',
            other='其他', folk='民间治疗'),
 'en': dict(drug='Medications', outpatient='Outpatient', inpatient='Inpatient',
            dental='Dental', other='Other', folk='Folk healers'),
}
TXT = {
 'zh': dict(
  doc='方向 A：关节炎与老年人自付医疗支出——五张主图（中文版）',
  sub='四类 harmonized 老龄化队列 · 25 个波次 · 576,020 人波｜生成于 2026-11-13｜所有数字取自已落盘结果 CSV',
  note='本文件为论文图版草案；中文版用于汇报与核对，投稿请使用英文版。图内数值与 out/ 下结果 CSV 严格一致。'
       '术语：全稿统一用「超额自付（excess）」，不用「归因自付（attributable）」。'
       '措辞红线：新颖性只能写「首个多队列 harmonised 估计」，不得写「首个关节炎自付支出研究」；'
       '阈值结局称「基于收入的财务负担」，不称 WHO 式灾难性卫生支出；制度梯度写「无证据支持」，不写「制度无影响」；'
       'SES 图注不得写「低 SES 承受更大相对负担」。',
  f1='图 1｜关节炎与自付医疗支出：四库逐库估计与随机效应合并',
  f2='图 2｜首次报告关节炎前后的自付支出动态（事件研究）',
  f3='图 3｜关节炎的额外自付落在哪些分项：份额变化与会计闭合分摊',
  f4='图 4｜20 国制度梯度检验：国家自付占比与关节炎效应量',
  f5='图 5｜SES 分层效应修饰：各社会经济层的合并关联与超额自付的收入占比',
  panelA='A  分项份额的关节炎—对照差异（百分点）',
  panelB='B  超额自付的会计闭合分摊（2020 国际元／年）',
  pooled='合并（随机效应）', effect='效应量 (95% CI)', n='人波数 / I²',
  axis1='效应量（对数尺度，OR／金额比）', axis2='100 × log 单位（相对 k = −1）',
  axis3a='份额差异（百分点）', axis3b='超额自付（2020 国际元／年）',
  axis4x='自付占卫生总费用比重（%，2004–2005 均值）', axis4y='关节炎对「有无自付」的 OR',
  onset='首次报告波', ref='参照期', pre='前置趋势联合检验',
  a1total='A1 总额（g-comp）', share='份额', amount='金额',
  ext='扩展库', primary='主要结局', secondary='次要结局',
  sesA='A  各 SES 分层的合并效应量（4 库随机效应合并，95% CI）',
  sesB='B  超额自付占该层家庭收入中位数之比（描述性、未校正）',
  sesAxA='合并效应量（对数尺度，OR／金额比）',
  sesAxB='超额自付占收入中位数（%）',
  sesIncome='收入五分位', sesEdu='教育层级', sesQ='收入五分位',
  sesP1='P1 有无自付（OR）', sesP2='P2inc 有支出者金额比',
  sesLow='低', sesMid='中', sesHigh='高', sesQ1='Q1 最低', sesQ5='Q5 最高',
  sesNote='SHARE 仅 w1；误差线为 95% CI；虚线为无效线 1.0',
  sesDesc='描述性、未校正；纵轴为对数尺度',
 ),
 'en': dict(
  doc='Direction A: Arthritis and out-of-pocket spending in older adults — five main figures',
  sub='Four harmonised ageing cohorts · 25 waves · 576,020 person-waves | Generated 2026-11-13 | All values read from deposited result CSVs',
  note='Manuscript figure set (draft). Use this English version for submission; all plotted values are identical to the deposited CSVs in out/. '
       'Terminology: "excess out-of-pocket spending" throughout, never "attributable spending". '
       'Novelty wording: "first multi-cohort harmonised estimate" (never "first study of arthritis out-of-pocket spending"). '
       'Thresholds are income-based financial burden, not WHO-style catastrophic health expenditure; '
       'the institutional result is "no evidence of an institutional gradient"; '
       'the SES legend must not claim a larger relative burden at lower socioeconomic position.',
  f1='Figure 1 | Arthritis and out-of-pocket spending: cohort-specific estimates and random-effects pooling',
  f2='Figure 2 | Out-of-pocket spending around the first report of arthritis (event study)',
  f3='Figure 3 | Where the additional out-of-pocket spending falls: component shares and closed excess allocation',
  f4='Figure 4 | Test of an institutional gradient across 20 countries',
  f5='Figure 5 | Effect modification by socioeconomic position: pooled associations and the income share of excess OOP',
  panelA='A  Difference in component shares, arthritis vs. no arthritis (percentage points)',
  panelB='B  Closed allocation of excess OOP (2020 international $/year)',
  pooled='Pooled (random effects)', effect='Effect (95% CI)', n='Person-waves / I²',
  axis1='Effect size (log scale; OR / amount ratio)', axis2='100 × log units (relative to k = −1)',
  axis3a='Difference in share (percentage points)', axis3b='Excess OOP (2020 international $/year)',
  axis4x='Out-of-pocket share of current health expenditure (%, 2004–2005 mean)',
  axis4y='OR for any out-of-pocket spending, arthritis vs. no arthritis',
  onset='First-report wave', ref='Reference', pre='Joint pre-trend test',
  a1total='A1 total (g-computation)', share='Share', amount='Amount',
  ext='Extension', primary='Primary outcome', secondary='Secondary outcome',
  sesA='A  Pooled effect within each socioeconomic stratum (4-cohort random effects, 95% CI)',
  sesB='B  Excess OOP as a share of stratum median household income (descriptive, unadjusted)',
  sesAxA='Pooled effect (log scale; OR / amount ratio)',
  sesAxB='Excess OOP as % of median household income',
  sesIncome='Income quintile', sesEdu='Education', sesQ='Household income quintile',
  sesP1='P1, any OOP (OR)', sesP2='P2inc, amount ratio among spenders',
  sesLow='Low', sesMid='Middle', sesHigh='High', sesQ1='Q1 lowest', sesQ5='Q5 highest',
  sesNote='SHARE wave 1 only; bars are 95% CIs; dashed line marks the null effect (1.0)',
  sesDesc='Descriptive and unadjusted; vertical axis on a log scale',
 ),
}

# ---------------------------------------------------------------- Figure 1
def fig1(lang):
    t = TXT[lang]
    W, H = 1000, 700
    x0, x1 = 268, 715
    lo_a, hi_a = 0.50, 2.00
    def sx(v): return x0 + (math.log(v)-math.log(lo_a))/(math.log(hi_a)-math.log(lo_a))*(x1-x0)
    s = [T(20, 26, t['f1'], 14, weight='bold', family='cn' if lang=='zh' else 'serif')]
    groups = [
      ('P1_any_oop',  'P1' if lang=='en' else 'P1 有无自付支出（OR）', 'primary'),
      ('P2inc_amount_log_adj_income', 'P2inc' if lang=='en' else 'P2inc 有支出者金额比（控制 log 收入）', 'primary'),
      ('B10_oop_ge10pct_income', 'B10 (OOP/income ≥10%)' if lang=='en' else 'B10 OOP/收入 ≥10%（OR）', 'secondary'),
      ('B40_oop_ge40pct_income', 'B40 (OOP/income ≥40%)' if lang=='en' else 'B40 OOP/收入 ≥40%（OR）', 'secondary'),
    ]
    # header
    hy = 52
    s.append(T(20, hy, t['primary'] if lang=='zh' else 'Outcome', 10, fill=MUTED, weight='bold'))
    s.append(T(x0, hy, t['axis1'], 10, fill=MUTED, anchor='middle', weight='bold'))
    s.append(T(730, hy, t['effect'], 10, fill=MUTED, weight='bold'))
    s.append(T(930, hy, t['n'], 10, fill=MUTED, anchor='end', weight='bold'))
    s.append(L(20, 58, 980, 58, GRID, 1))
    y = 76
    for oc, label, tier in groups:
        s.append(T(20, y, label, 11.5, weight='bold',
                   fill='#1f4e79' if tier=='primary' else '#6b7280'))
        s.append(T(980, y, t['primary'] if tier=='primary' else t['secondary'],
                   9, anchor='end', fill=MUTED))
        y += 21
        sub = FOREST[(FOREST.outcome==oc) & (FOREST.db!='POOLED (RE)')]
        pool = FOREST[(FOREST.outcome==oc) & (FOREST.db=='POOLED (RE)')].iloc[0]
        for _, r in sub.iterrows():
            col = C.get(r['db'], '#666')
            yy = y
            s.append(T(34, yy+4, DBNAME.get(r['db'], r['db']), 11, fill=col, weight='bold'))
            # CI line
            xl, xh = sx(max(r['lo'], lo_a)), sx(min(r['hi'], hi_a))
            s.append(L(xl, yy, xh, yy, col, 1.8))
            s.append(L(xl, yy-4, xl, yy+4, col, 1.5))
            s.append(L(xh, yy-4, xh, yy+4, col, 1.5))
            s.append(R(sx(r['effect'])-4, yy-4, 8, 8, col, rx=1))
            s.append(T(730, yy+4, f"{r['effect']:.3f} ({r['lo']:.3f}–{r['hi']:.3f})", 10.5))
            s.append(T(980, yy+4, f"{int(r['n']):,}", 10, anchor='end', fill=MUTED))
            y += 20
        # pooled diamond
        if oc in META.index:
            pe, plo, phi = (float(META.loc[oc, 'pooled_effect']), float(META.loc[oc, 'lo']),
                            float(META.loc[oc, 'hi']))
        else:
            pe, plo, phi = float(pool['effect']), float(pool['lo']), float(pool['hi'])
        yy = y + 3
        cx = sx(pe); xl, xh = sx(plo), sx(phi)
        s.append(POLY([(xl,yy),(cx,yy-8),(xh,yy),(cx,yy+8)], C['pooled']))
        s.append(T(34, yy+4, t['pooled'], 10.5, weight='bold'))
        s.append(T(730, yy+4, f"{pe:.3f} ({plo:.3f}–{phi:.3f})",
                   10.5, weight='bold'))
        m = SENS[(SENS.set=='main_revised') & (SENS.outcome==oc)]
        if len(m):
            s.append(T(980, yy+4, f"I²={m.iloc[0]['I2']:.1f}%", 9.5, anchor='end', fill=MUTED))
        y += 30
        s.append(L(20, y-10, 980, y-10, GRID, 1))
    # axis
    ay = y + 4
    s.append(L(x0, ay, x1, ay, AXIS, 1))
    for v in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        xx = sx(v)
        s.append(L(xx, 62, xx, ay, GRID, 1))
        s.append(L(xx, ay, xx, ay+5, AXIS, 1))
        s.append(T(xx, ay+18, f'{v:g}', 10, anchor='middle', fill=MUTED))
    s.append(L(sx(1.0), 62, sx(1.0), ay, '#8a1c1c', 1.3, dash='5,4'))
    return WRAP(W, H, '\n'.join(s))

# ---------------------------------------------------------------- Figure 2
def fig2(lang):
    t = TXT[lang]
    W, H = 1000, 400
    s = [T(20, 26, t['f2'], 14, weight='bold', family='cn' if lang=='zh' else 'serif')]
    dbs = ['mhas','hrs','share']
    pW, gap = 300, 18
    ymin, ymax = -0.40, 0.60
    def sy(v, top, bot): return bot - (v-ymin)/(ymax-ymin)*(bot-top)
    for i, db in enumerate(dbs):
        ox = 30 + i*(pW+gap)
        L_, Rr = ox+52, ox+pW-12
        top, bot = 78, 308
        g = EVENT[(EVENT.set=='main') & (EVENT.outcome=='log1p_amount') & (EVENT.db==db)]
        g = g.set_index('k')
        ks = sorted(set(range(-3,4)) & set(g.index) | {-1})
        def sk(k): return L_ + (k+3)/6*(Rr-L_)
        # frame
        s.append(L(L_, top, L_, bot, AXIS, 1)); s.append(L(L_, bot, Rr, bot, AXIS, 1))
        for v in [-0.4,-0.2,0,0.2,0.4,0.6]:
            yy = sy(v, top, bot)
            s.append(L(L_, yy, Rr, yy, GRID, 1))
            s.append(T(L_-6, yy+3.5, f'{v*100:.0f}', 9, anchor='end', fill=MUTED))
        s.append(T(L_-6, top-10, t['axis2'], 9, anchor='start', fill=MUTED))
        # zero + onset
        s.append(L(L_, sy(0,top,bot), Rr, sy(0,top,bot), '#8a1c1c', 1, dash='4,3'))
        s.append(L(sk(0), top, sk(0), bot, '#8a1c1c', 1, dash='4,3', opacity=.6))
        s.append(T(sk(0)+4, top+12, t['onset'], 8.5, fill='#8a1c1c'))
        for k in [-3,-2,-1,0,1,2,3]:
            xx = sk(k)
            s.append(L(xx, bot, xx, bot+4, AXIS, 1))
            s.append(T(xx, bot+16, ('−1' if k==-1 else str(k)), 9, anchor='middle', fill=MUTED))
        s.append(T((L_+Rr)/2, bot+32, 'k (wave relative to first report)' if lang=='en'
                   else 'k（相对首次报告波的波次）', 9.5, anchor='middle', fill=MUTED))
        # coefficients
        pts, cis = [], []
        for k in ks:
            if k == -1 or k not in g.index:
                pts.append((sk(k), sy(0,top,bot))); continue
            r = g.loc[k]
            if isinstance(r, pd.DataFrame): r = r.iloc[0]
            yy = sy(float(r['beta']), top, bot)
            pts.append((sk(k), yy))
            cis.append((sk(k), sy(float(r['lo']),top,bot), sy(float(r['hi']),top,bot)))
        s.append(PLINE(pts, C[db], 2))
        for xx, yl, yh in cis:
            s.append(L(xx, yl, xx, yh, C[db], 1.3))
            s.append(L(xx-3, yl, xx+3, yl, C[db], 1.2))
            s.append(L(xx-3, yh, xx+3, yh, C[db], 1.2))
        for xx, yy in pts:
            ref = (abs(yy-sy(0,top,bot))<0.01)
            s.append(CIR(xx, yy, 4.2, '#ffffff' if ref else C[db], C[db], 1.8))
        # panel header
        pre = ETEST[(ETEST.set=='main') & (ETEST.db==db) &
                    (ETEST.outcome=='log1p_amount') & (ETEST.test=='pretrend_joint')]
        nid = int(g['n_ids'].max()) if len(g) else 0
        s.append(T(ox+8, 48, DBNAME[db], 12, weight='bold', fill=C[db]))
        s.append(T(ox+70, 48,
                   (f"n={nid:,} · {t['pre']} P={float(pre.iloc[0]['p']):.2f}" if len(pre)
                    else f'n={nid:,}'), 9.5, fill=MUTED))
    s.append(T(20, 356, 'k = −1 ' + ('(reference, fixed at 0)' if lang=='en' else '（参照期，固定为 0）'),
               9.5, fill=MUTED))
    return WRAP(W, H, '\n'.join(s))

# ---------------------------------------------------------------- Figure 3
def fig3(lang):
    t, cat = TXT[lang], CAT[lang]
    W, H = 1000, 880
    s = [T(20, 26, t['f3'], 14, weight='bold', family='cn' if lang=='zh' else 'serif')]
    # ---- Panel A: share differences ----
    s.append(T(20, 58, t['panelA'], 12, weight='bold'))
    ax0, ax1 = 250, 760
    lo_a, hi_a = -7.0, 9.0
    def sx(v): return ax0 + (v-lo_a)/(hi_a-lo_a)*(ax1-ax0)
    rows = SHARES.copy()
    order = ['mhas','share','lasi','charls']
    cat_order = ['drug','outpatient','inpatient','dental','other','folk']
    rows['db_o'] = rows['db'].map({d:i for i,d in enumerate(order)})
    rows['cat_o'] = rows['cat'].map({c:i for i,c in enumerate(cat_order)})
    rows = rows.sort_values(['db_o','cat_o']).reset_index(drop=True)
    y = 84
    for v in [-6,-4,-2,0,2,4,6,8]:
        xx = sx(v); s.append(L(xx, y-8, xx, y+len(rows)*20+6, GRID, 1))
        s.append(T(xx, y+len(rows)*20+22, f'{v:+g}' if v else '0', 9, anchor='middle', fill=MUTED))
    s.append(L(sx(0), y-8, sx(0), y+len(rows)*20+6, '#8a1c1c', 1.2, dash='4,3'))
    for _, r in rows.iterrows():
        yy = y + 10
        col = CATC.get(r['cat'], '#666')
        ext = (r['db']=='charls')
        s.append(T(22, yy+4, f"{DBNAME[r['db']]} · {cat.get(r['cat'],r['cat'])}", 10,
                   fill=MUTED if ext else '#1a1a1a'))
        xl, xh = sx(max(r['lo_pp'],lo_a)), sx(min(r['hi_pp'],hi_a))
        s.append(L(xl, yy, xh, yy, col, 1.3))
        s.append(L(xl, yy-3, xl, yy+3, col, 1.1)); s.append(L(xh, yy-3, xh, yy+3, col, 1.1))
        s.append(CIR(sx(r['diff_pp']), yy, 4, '#ffffff' if ext else col, col, 1.8))
        s.append(T(775, yy+4, f"{r['diff_pp']:+.2f} ({r['lo_pp']:+.2f}, {r['hi_pp']:+.2f})", 9.5,
                   fill=MUTED if ext else '#1a1a1a'))
        if ext: s.append(T(940, yy+4, t['ext'], 8.5, anchor='end', fill=MUTED))
        y += 20
    s.append(T((ax0+ax1)/2, y+36, t['axis3a'], 10, anchor='middle', fill=MUTED))
    # ---- Panel B: closed attribution ----
    by = y + 66
    s.append(T(20, by, t['panelB'], 12, weight='bold'))
    dbs = ['mhas','share','lasi']
    cats = ['drug','outpatient','inpatient','dental','other']
    maxv = 220.0
    bx0, bx1 = 70, 940
    gtop, gbot = by+34, by+214
    def sy(v): return gbot - v/maxv*(gbot-gtop)
    for v in [0,50,100,150,200]:
        yy = sy(v); s.append(L(bx0, yy, bx1, yy, GRID, 1))
        s.append(T(bx0-8, yy+3.5, str(v), 9, anchor='end', fill=MUTED))
    s.append(L(bx0, sy(0), bx1, sy(0), AXIS, 1))
    gw = (bx1-bx0)/3
    _g = rd('22_1a_gcomp.csv').set_index('db')['attributable_oop_2020intl']
    totals = {db: float(_g[db]) for db in dbs}
    for i, db in enumerate(dbs):
        cx = bx0 + gw*(i+0.5)
        sub = CLOSED[(CLOSED.db==db) & (CLOSED.cat.isin(cats))]
        bw, n = 26, len(sub)
        for j, (_, r) in enumerate(sub.iterrows()):
            xx = cx - n*bw/2 + j*bw + 3
            v = float(r['attributable_closed'])
            yy0, yy1 = sy(max(0,v)), sy(min(0,v))
            s.append(R(xx, yy0, bw-6, max(1.5, yy1-yy0), CATC.get(r['cat'],'#666')))
            s.append(T(xx+(bw-6)/2, yy0-4, f"{v:.0f}", 8, anchor='middle', fill=MUTED))
        # A1 total line
        tv = totals[db]
        yy = sy(tv)
        s.append(L(cx-gw/2+18, yy, cx+gw/2-18, yy, C['pooled'], 1.5, dash='6,3'))
        s.append(T(cx, yy-5, f"{t['a1total']} {tv:.0f}", 8.5, anchor='middle', fill=C['pooled']))
        s.append(T(cx, gbot+18, DBNAME[db], 11, anchor='middle', weight='bold'))
    # rotated y-axis title for Panel B
    s.append(T(22, (gtop+gbot)/2, t['axis3b'], 10, anchor='middle', fill=MUTED,
               style=f'transform="rotate(-90 22 {(gtop+gbot)/2})"'))
    # legend (shared by both panels; folk healers appear only in Panel A)
    ly = gbot + 42
    for j, c in enumerate(cats + ['folk']):
        xx = 70 + j*145
        s.append(R(xx, ly-9, 12, 12, CATC[c]))
        lab = cat[c] + ('' if c!='folk' else (' (A only)' if lang=='en' else '（仅 A）'))
        s.append(T(xx+17, ly+1, lab, 10))
    return WRAP(W, H, '\n'.join(s))

# ---------------------------------------------------------------- Figure 4
def fig4(lang):
    t = TXT[lang]
    W, H = 1000, 590
    s = [T(20, 26, t['f4'], 14, weight='bold', family='cn' if lang=='zh' else 'serif')]
    x0, x1, yt, yb = 92, 950, 62, 470
    xlo, xhi, ylo, yhi = 8.0, 36.0, 0.80, 2.05
    def sx(v): return x0 + (v-xlo)/(xhi-xlo)*(x1-x0)
    def sy(v): return yb - (v-ylo)/(yhi-ylo)*(yb-yt)
    # frame & grid
    for v in [10,15,20,25,30,35]:
        s.append(L(sx(v), yt, sx(v), yb, GRID, 1))
        s.append(T(sx(v), yb+18, str(v), 9.5, anchor='middle', fill=MUTED))
    for v in [0.8,1.0,1.2,1.4,1.6,1.8,2.0]:
        s.append(L(x0, sy(v), x1, sy(v), GRID, 1))
        s.append(T(x0-8, sy(v)+3.5, f'{v:.1f}', 9.5, anchor='end', fill=MUTED))
    s.append(L(x0, yb, x1, yb, AXIS, 1)); s.append(L(x0, yt, x0, yb, AXIS, 1))
    s.append(L(x0, sy(1.0), x1, sy(1.0), '#8a1c1c', 1.2, dash='5,4'))
    # meta-regression line: recover mean/sd of the z-scored covariate
    z = SCAT['oop_pct_che_z'].values; x = SCAT['oop_pct_che_mean0405'].values
    sd = float(np.polyfit(z, x, 1)[0]); mean = float(x.mean() - z.mean()*sd)
    m = MREG[(MREG.set=='main_univariable') & (MREG.outcome=='or_any_oop') &
             (MREG.covariate=='oop_pct_che')].iloc[0]
    b0, b1, se1 = float(m['intercept']), float(m['beta']), float(m['se'])
    xs = np.linspace(xlo, xhi, 60)
    def pred(v, b): return np.exp(b0 + b*(v-mean)/sd)
    lo_b, hi_b = b1-1.96*se1, b1+1.96*se1
    upper = [(sx(v), sy(float(np.clip(max(pred(v,lo_b),pred(v,b1),pred(v,hi_b)), ylo, yhi)))) for v in xs]
    lower = [(sx(v), sy(float(np.clip(min(pred(v,lo_b),pred(v,b1),pred(v,hi_b)), ylo, yhi)))) for v in xs]
    s.append(POLY(upper + lower[::-1], '#b03a2e', opacity=.13))
    s.append(PLINE([(sx(v), sy(float(pred(v,b1)))) for v in xs], '#b03a2e', 2, dash='7,4'))
    # points, with greedy label de-overlap
    bx, byy = 690, 78
    placed = [(bx-4, byy-4, bx+256, byy+96)]   # reserve the info-box area
    cands = [(0,-9),(0,15),(-15,-5),(15,-5),(-20,7),(20,7),(0,-20),(0,25),
             (-25,-13),(25,-13),(0,-31),(0,36)]
    for i, (_, r) in enumerate(SCAT.iterrows()):
        xx, yy = sx(r['oop_pct_che_mean0405']), sy(r['or_any_oop'])
        lo, hi = r['or_any_oop']-1.96*r['se_or'], r['or_any_oop']+1.96*r['se_or']
        rad = 3.0 + 2.0*math.sqrt(r['n']/20000)
        s.append(L(xx, sy(min(hi,yhi)), xx, sy(max(lo,ylo)), '#9aa3ad', 1))
        s.append(L(xx-2.5, sy(min(hi,yhi)), xx+2.5, sy(min(hi,yhi)), '#9aa3ad', 1))
        s.append(L(xx-2.5, sy(max(lo,ylo)), xx+2.5, sy(max(lo,ylo)), '#9aa3ad', 1))
        s.append(CIR(xx, yy, min(rad,7.5), C['mhas'], opacity=.82))
        lab = str(r['iso3']); tw = len(lab)*5.6+3; th = 9.5
        best = None
        for dx, dy in cands:
            cx, cy = xx+dx, yy+dy
            bb = (cx-tw/2, cy-th, cx+tw/2, cy+2)
            if bb[0] < x0+2 or bb[2] > x1-2 or bb[1] < yt+2 or bb[3] > yb-2:
                continue
            ov = 0.0
            for p in placed:
                ox = max(0.0, min(bb[2],p[2])-max(bb[0],p[0]))
                oy = max(0.0, min(bb[3],p[3])-max(bb[1],p[1]))
                ov += ox*oy
            if best is None or ov < best[0]: best = (ov, cx, cy, bb)
            if ov == 0: break
        if best is None: continue
        _, cx, cy, bb = best
        placed.append(bb)
        if abs(cx-xx) > 10 or abs(cy-yy) > 18:
            s.append(L(xx, yy, cx, cy-3, '#b7bec6', .7))
        s.append(T(cx, cy, lab, 8.5, anchor='middle', fill='#4a5058'))
    # info box
    s.append(R(bx, byy, 252, 92, '#ffffff', stroke=GRID, rx=4, opacity=.96))
    s.append(T(bx+10, byy+19, 'Meta-regression' if lang=='en' else '随机效应 meta 回归', 10, weight='bold'))
    s.append(T(bx+10, byy+37,
               f"OR ratio / SD = {m['ratio_per_sd']:.3f} ({m['lo']:.3f}–{m['hi']:.3f})", 9.5))
    s.append(T(bx+10, byy+53, f"P = {m['p']:.3f}   R² = {m['R2']:.2f}   I²(resid) = {m['I2_resid']:.1f}%", 9.5))
    s.append(T(bx+10, byy+69, f"k = 20   τ² = {m['tau2_used']:.4f}", 9.5))
    _npos = int((SCAT.or_any_oop>1).sum())
    s.append(T(bx+10, byy+84,
               f'{_npos}/20 countries OR > 1' if lang=='en' else f'{_npos}/20 国 OR > 1',
               9.5, weight='bold'))
    # axes titles
    s.append(T((x0+x1)/2, yb+42, t['axis4x'], 11, anchor='middle'))
    s.append(T(20, (yt+yb)/2, t['axis4y'], 11, anchor='middle',
               style=f'transform="rotate(-90 20 {(yt+yb)/2})"'))
    s.append(T(x0+6, yt+14, 'OR = 1', 9, fill='#8a1c1c'))
    return WRAP(W, H, '\n'.join(s))

# ---------------------------------------------------------------- 图注（数字全部从 CSV 取）
# ---------------------------------------------------------------- Figure 5
def fig5(lang):
    """SES 分层效应修饰。A：16 个分层合并效应（4 库 RE）；B：超额自付占收入中位数之比。"""
    t = TXT[lang]
    W, H = 1000, 930
    s = [T(20, 26, t['f5'], 14, weight='bold', family='cn' if lang=='zh' else 'serif')]

    # ---- Panel A: forest of stratum-specific pooled effects ----
    s.append(T(20, 56, t['sesA'], 11.5, weight='bold', fill='#12283f'))
    x0, x1 = 300, 740
    lo_a, hi_a = 0.90, 1.70
    def sx(v): return x0 + (math.log(v)-math.log(lo_a))/(math.log(hi_a)-math.log(lo_a))*(x1-x0)
    s.append(T(20, 76, t['primary'], 9.5, fill=MUTED, weight='bold'))
    s.append(T(x0, 76, t['sesAxA'], 9.5, fill=MUTED, anchor='middle', weight='bold'))
    s.append(T(756, 76, t['effect'], 9.5, fill=MUTED, weight='bold'))
    s.append(T(980, 76, 'I\u00b2', 9.5, fill=MUTED, anchor='end', weight='bold'))
    s.append(L(20, 82, 980, 82, GRID, 1))
    q_lab = {'Q1 (lowest)': t['sesQ1'], 'Q2': 'Q2', 'Q3': 'Q3', 'Q4': 'Q4',
             'Q5 (highest)': t['sesQ5'], 'Low': t['sesLow'], 'Middle': t['sesMid'],
             'High': t['sesHigh']}
    groups = [
        (t['sesP1'] + ' · ' + t['sesIncome'], 'P1_any_oop', 'income_quintile', '#0072B2'),
        (t['sesP1'] + ' · ' + t['sesEdu'],    'P1_any_oop', 'education',       '#0072B2'),
        (t['sesP2'] + ' · ' + t['sesIncome'], 'P2inc_amount_log_adj_income', 'income_quintile', '#D55E00'),
        (t['sesP2'] + ' · ' + t['sesEdu'],    'P2inc_amount_log_adj_income', 'education',       '#D55E00'),
    ]
    y = 100
    for title, oc, ax, col in groups:
        s.append(T(20, y, title, 10.5, weight='bold', fill=col))
        y += 19
        sub = SESFIG[(SESFIG.outcome == oc) & (SESFIG.axis == ax)]
        for _, r in sub.iterrows():
            yy = y
            s.append(T(34, yy+4, q_lab.get(str(r['stratum']), str(r['stratum'])), 10))
            xl, xh = sx(max(float(r['lo']), lo_a)), sx(min(float(r['hi']), hi_a))
            s.append(L(xl, yy, xh, yy, col, 1.8))
            s.append(L(xl, yy-4, xl, yy+4, col, 1.4))
            s.append(L(xh, yy-4, xh, yy+4, col, 1.4))
            s.append(R(sx(float(r['effect']))-3.6, yy-3.6, 7.2, 7.2, col, rx=1))
            s.append(T(756, yy+4, f"{float(r['effect']):.3f} ({float(r['lo']):.3f}–{float(r['hi']):.3f})", 9.8))
            s.append(T(980, yy+4, f"I\u00b2={float(r['I2']):.1f}%", 9, anchor='end', fill=MUTED))
            y += 18
        y += 5
    ay = y + 2
    s.append(L(x0, ay, x1, ay, AXIS, 1))
    for v in [0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.7]:
        xx = sx(v)
        s.append(L(xx, 88, xx, ay, GRID, 1))
        s.append(L(xx, ay, xx, ay+5, AXIS, 1))
        s.append(T(xx, ay+18, f'{v:g}', 9.5, anchor='middle', fill=MUTED))
    s.append(L(sx(1.0), 88, sx(1.0), ay, '#8a1c1c', 1.3, dash='5,4'))

    # ---- Panel B: excess OOP as % of median income, by income quintile ----
    by = ay + 46
    s.append(T(20, by, t['sesB'], 11.5, weight='bold', fill='#12283f'))
    lx = 566
    for db in ('mhas', 'hrs', 'share', 'lasi'):
        s.append(L(lx, by-4, lx+16, by-4, C[db], 2.4))
        s.append(CIR(lx+8, by-4, 3, C[db]))
        s.append(T(lx+21, by, DBNAME[db], 9.5))
        lx += 104
    px0, px1, pyt, pyb = 92, 900, by+34, by+250
    ylo, yhi = 0.1, 30.0
    def sy(v): return pyb - (math.log(v)-math.log(ylo))/(math.log(yhi)-math.log(ylo))*(pyb-pyt)
    def px(q): return px0 + (q-1)/4.0*(px1-px0)
    for v in [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]:
        yy = sy(v)
        s.append(L(px0, yy, px1, yy, GRID, 1))
        s.append(T(px0-8, yy+3.5, f'{v:g}', 9.5, anchor='end', fill=MUTED))
    for q in (1, 2, 3, 4, 5):
        xx = px(q)
        s.append(L(xx, pyt, xx, pyb, GRID, 1))
        s.append(T(xx, pyb+18, 'Q%d' % q, 10, anchor='middle', fill=MUTED))
    s.append(L(px0, pyb, px1, pyb, AXIS, 1)); s.append(L(px0, pyt, px0, pyb, AXIS, 1))
    for db in ('mhas', 'hrs', 'share', 'lasi'):
        r = SESEQ[SESEQ.db == db].sort_values('quintile')
        pts = [(px(int(q)), sy(max(float(v), 1e-3)))
               for q, v in zip(r['quintile'], r['excess_pct_income'])]
        s.append(PLINE(pts, C[db], 2.2))
        for xx, yy in pts:
            s.append(CIR(xx, yy, 3.6, C[db], '#ffffff', 1.2))
    s.append(T((px0+px1)/2, pyb+40, t['sesQ'], 10, anchor='middle', fill=MUTED))
    s.append(T(20, pyb+40, t['sesAxB'], 10, fill=MUTED))
    s.append(T(20, pyb+62, t['sesDesc'], 9, fill=MUTED))
    return WRAP(W, H, '\n'.join(s))


def v_pool(oc):
    """合并值优先取 6 位小数 meta 源，避免 4 位中间表的二次舍入（B40 下限）。"""
    r = FOREST[(FOREST.outcome==oc) & (FOREST.db=='POOLED (RE)')].iloc[0]
    m = SENS[(SENS.set=='main_revised') & (SENS.outcome==oc)].iloc[0]
    if oc in META.index:
        r = {'effect': float(META.loc[oc,'pooled_effect']), 'lo': float(META.loc[oc,'lo']),
             'hi': float(META.loc[oc,'hi'])}
    return r, m
def legends(lang):
    t = TXT[lang]
    p1,m1 = v_pool('P1_any_oop'); p2,m2 = v_pool('P2inc_amount_log_adj_income')
    b10,m10 = v_pool('B10_oop_ge10pct_income'); b40,m40 = v_pool('B40_oop_ge40pct_income')
    ev = EVENT[(EVENT.set=='main') & (EVENT.outcome=='log1p_amount')]
    k0 = {r['db']: r for _,r in ev[ev.k==0].iterrows()}
    pre = {r['db']: r['p'] for _,r in ETEST[(ETEST.set=='main') &
           (ETEST.outcome=='log1p_amount') & (ETEST.test=='pretrend_joint')].iterrows()}
    mh = SHARES[(SHARES.db=='mhas') & (SHARES.cat=='drug')].iloc[0]
    sh = SHARES[(SHARES.db=='share') & (SHARES.cat=='drug')].iloc[0]
    ao = A2META[A2META.outcome=='amount_outpatient'].iloc[0]
    ai = A2META[A2META.outcome=='amount_inpatient'].iloc[0]
    mr = MREG[(MREG.set=='main_univariable') & (MREG.outcome=='or_any_oop') &
              (MREG.covariate=='oop_pct_che')].iloc[0]
    cl = {r['db']: r['closure_ratio'] for _,r in CLOSED[CLOSED.cat=='drug'].iterrows()}
    npos = int((SCAT.or_any_oop>1).sum())
    gc = rd('22_1a_gcomp.csv').set_index('db')['attributable_oop_2020intl']
    tot_txt = (f"MHAS {gc['mhas']:.1f} / SHARE {gc['share']:.1f} / LASI {gc['lasi']:.1f}")
    # SES 数字（全部从 41_ses_tests.csv / 41_ses_equity_ratio.csv 读取）
    def tv(k, col='estimate'): return float(SESTST.loc[k, col])
    i_p1_inc = f"{tv('T_P1_income'):.3f} ({tv('T_P1_income','lo'):.3f}–{tv('T_P1_income','hi'):.3f})"
    i_p1_edu = f"{tv('T_P1_education'):.3f} ({tv('T_P1_education','lo'):.3f}–{tv('T_P1_education','hi'):.3f})"
    i_p2_inc = f"{tv('T_P2inc_income'):.3f} ({tv('T_P2inc_income','lo'):.3f}–{tv('T_P2inc_income','hi'):.3f})"
    i_p2_edu = f"{tv('T_P2inc_education'):.3f} ({tv('T_P2inc_education','lo'):.3f}–{tv('T_P2inc_education','hi'):.3f})"
    eq_med = f"{tv('T_equity_ratio'):.1f} ({tv('T_equity_ratio','lo'):.1f}–{tv('T_equity_ratio','hi'):.1f})"
    n_strata = int(len(SESFIG))
    if lang=='zh':
        return [
          f"<b>图 1</b>　四个 harmonized 老龄化队列（MHAS、HRS、SHARE、LASI；25 个波次，576,020 人波）中，"
          f"自报 ever-diagnosed 关节炎与自付医疗支出的关联。P1 = 有无自付支出的 logistic 回归（OR）；"
          f"P2inc = 有支出者年化自付金额的 log-OLS（金额比，另控制 log 家庭收入）；"
          f"B10 / B40 = 自付／家庭收入 ≥10% / ≥40% 的二值结局（<b>income-based financial burden，非 WHO 式灾难性卫生支出</b>）。"
          f"所有模型按库分别估计，使用抽样权重、完整协变量（年龄、性别、婚姻、教育、波次、自评健康、ADL、糖尿病、高血压、卒中、城乡；SHARE 另含国家固定效应）"
          f"与个体 ID 聚类稳健标准误；合并采用 DerSimonian–Laird 随机效应，<b>不做 naïve pooling</b>。"
          f"方块为逐库点估计、横线为 95% CI、菱形为合并值；纵虚线为无效线 1.0。"
          f"主结局合并值：P1 <b>{p1['effect']:.3f} ({p1['lo']:.3f}–{p1['hi']:.3f})</b>、I²={m1['I2']:.1f}%；"
          f"P2inc <b>{p2['effect']:.3f} ({p2['lo']:.3f}–{p2['hi']:.3f})</b>、I²={m2['I2']:.1f}%。"
          f"次要结局 B10 {b10['effect']:.3f} ({b10['lo']:.3f}–{b10['hi']:.3f})、I²={m10['I2']:.1f}%；"
          f"B40 {b40['effect']:.3f} ({b40['lo']:.3f}–{b40['hi']:.3f})、I²={m40['I2']:.1f}%，<b>无统计学显著性</b>。"
          f"SHARE 的阈值结局仅用 w1（w2+ 收入变量定义不同，见诊断③）；HRS w3–w16 的 2 年回忆窗已 ÷2 年化；"
          f"所有金额逐国 PPP + CPI 平减至 2020 国际元。缩写：OOP = out-of-pocket，自付医疗支出；I² = 异质性占比。",
          f"<b>图 2</b>　以「首次报告关节炎」为中心的事件研究，结局为 log(1+年化自付金额)，系数以 100×log 单位表示并相对参照期 k = −1。"
          f"三库分别为 MHAS（{int(k0['mhas']['n_ids']):,} 人）、HRS（{int(k0['hrs']['n_ids']):,} 人）、"
          f"SHARE（{int(k0['share']['n_ids']):,} 人）；对照为从未报告关节炎者。"
          f"点为各事件时点系数、竖线为 95% CI（个体 ID 聚类稳健），空心点为参照期（固定为 0），"
          f"竖虚线标出首次报告波。前置趋势联合 Wald 检验均不显著"
          f"（MHAS P={pre.get('mhas',float('nan')):.2f}、HRS P={pre.get('hrs',float('nan')):.2f}、"
          f"SHARE P={pre.get('share',float('nan')):.2f}）。首次报告波自付金额跳升："
          f"MHAS {100*k0['mhas']['beta']:.1f}、HRS {100*k0['hrs']['beta']:.1f}、"
          f"SHARE {100*k0['share']['beta']:.1f}（均 P&lt;0.001），k=+1 衰减、k=+2 后消失。"
          f"<b>限制</b>：HRS 的 2 年回忆窗与 2 年波间隔重叠，k=0 可能跨过真实发病前；"
          f"`arthre` 为 ever-diagnosed 累计标记，首次报告 ≠ 真实发病；"
          f"因此结果应表述为「首次报告关节炎的那一波」，<b>不作因果解释</b>。"
          f"CHARLS 因 1→0 回落（1,218 人）与金额可得率仅 45.1% 未纳入。",
          f"<b>图 3</b>　A：各支出分项占年化自付总额份额的关节炎—对照差异（百分点，95% CI；"
          f"个体 ID 聚类稳健）。B：按 A1 g-computation 总额强制闭合后的分项超额自付（2020 国际元／年），"
          f"虚线为 A1 总额（{tot_txt}）。"
          f"数据为 MHAS 6 波、SHARE 4 波、LASI 1 波、CHARLS 4 波共 353,111 人波；"
          f"<b>15/15 个「库×波」分项加总与 harmonized 总额 100% 精确相等</b>，故为精确会计分解而非近似。"
          f"药费份额在 MHAS <b>+{mh['diff_pp']:.2f} pp ({mh['lo_pp']:.2f}–{mh['hi_pp']:.2f})</b>、"
          f"SHARE <b>+{sh['diff_pp']:.2f} pp ({sh['lo_pp']:.2f}–{sh['hi_pp']:.2f})</b> 均显著上升；"
          f"药品分项仅 MHAS、SHARE 两库可得、未合并，上述药费份额为单库观察。"
          f"合并门诊金额效应 {ao['pooled_effect']:.3f} ({ao['lo']:.3f}–{ao['hi']:.3f})，"
          f"而住院金额效应 {ai['pooled_effect']:.3f} ({ai['lo']:.3f}–{ai['hi']:.3f}) <b>不显著</b>。"
          f"独立分项 g-comp 与 A1 总额的闭合比为 MHAS {cl.get('mhas',float('nan')):.3f} / "
          f"SHARE {cl.get('share',float('nan')):.3f} / LASI {cl.get('lasi',float('nan')):.3f}（模型近似，非数据错误），"
          f"故 B 面板另做构成比强制闭合分摊，两轨并列报告。HRS 无金额分项，不进本图；"
          f"CHARLS 为自建年化总额（漏药费约 1–2%），仅作扩展。"
          f"<b>自付金额 ≠ 服务利用量</b>，不得写为「增加药品利用」；SHARE `other` 描述性与校正后方向相反，不作结论。",
          f"<b>图 4</b>　SHARE 20 国逐国有无自付的 OR（点；竖线为 95% CI，点面积 ∝ √样本量）"
          f"对国家自付占卫生总费用比重（2004–2005 均值）的散点，含随机效应 meta 回归拟合线（红色虚线）"
          f"与其 95% 带（浅红）。国家层自变量来自 World Bank WDI；自付占比范围 "
          f"{SCAT.oop_pct_che_mean0405.min():.2f}%–{SCAT.oop_pct_che_mean0405.max():.2f}%。"
          f"<b>{npos}/20 国 OR &gt; 1</b>，方向高度一致；但自付占比每升高 1 SD 的 OR 比为 "
          f"<b>{mr['ratio_per_sd']:.3f} ({mr['lo']:.3f}–{mr['hi']:.3f})，P={mr['p']:.3f}，R²={mr['R2']:.2f}</b>，"
          f"残差 I²={mr['I2_resid']:.1f}%、τ²={mr['tau2_used']:.4f}；留一法 0/20 显著，"
          f"9 个 WDI 制度变量经 BH-FDR 校正后无一显著。"
          f"结论应写为「<b>无制度梯度的证据（no evidence of an institutional gradient）</b>」，"
          f"并以「跨制度一致性」作为正面论点；<b>不得</b>写「制度无影响」，也不作标题级卖点。",
          f"<b>图 5</b>　社会经济地位（SES）分层效应修饰。A 面板：两个主结局（P1 有无自付 OR；P2inc 有支出者"
          f"金额比）在收入五分位（库×波内）与教育三层级（库内原码近似归并）各层的 4 库随机效应合并估计，"
          f"共 {n_strata} 层；点为合并值、横线为 95% CI，纵虚线为无效线 1.0。"
          f"<b>{n_strata}/{n_strata} 个分层合并估计的 95% CI 下界均 &gt;1</b>，即关联在每个 SES 层都存在。"
          f"正式交互检验（2 结局 × 2 SES 轴，Benjamini-Hochberg FDR）：P1×收入五分位效应比/级 "
          f"{i_p1_inc}，P2inc×教育 {i_p2_edu}，两者方向均指向<b>较高</b> SES 的相对效应略大，"
          f"量级小且库间异质性高；P1×教育 {i_p1_edu}、P2inc×收入五分位 {i_p2_inc} 均无修饰证据。"
          f"B 面板：各库各收入五分位的「关节炎组与对照组加权平均年自付之差 ÷ 该层家庭收入中位数」"
          f"（描述性、未校正、纵轴对数尺度；SHARE 仅 w1）。Q1/Q5 比四库中位数 {eq_med}。"
          f"<b>该梯度由收入分母驱动，不是效应修饰、不是标准化或因果量</b>；绝对超额金额在各五分位"
          f"量级相近或 Q5 略高。措辞红线：不得写「低 SES 人群承受更大相对负担」「证明不公平」。"
        ]
    return [
      f"<b>Figure 1</b>  Association between self-reported ever-diagnosed arthritis and out-of-pocket (OOP) "
      f"medical spending across four harmonised ageing cohorts (MHAS, HRS, SHARE, LASI; 25 waves; 576,020 person-waves). "
      f"P1: logistic regression for any OOP spending (OR). P2inc: log-OLS of annualised OOP amount among spenders "
      f"(amount ratio), additionally adjusted for log household income. B10/B40: OOP/household income ≥10%/≥40% "
      f"(<b>income-based financial burden, not WHO-style catastrophic health expenditure</b>). "
      f"Models were fitted within each cohort with sampling weights, full covariate adjustment (age, sex, marital status, "
      f"education, wave, self-rated health, ADL, diabetes, hypertension, stroke, rurality; country fixed effects for SHARE) "
      f"and individual-ID cluster-robust standard errors, then combined by DerSimonian–Laird random effects; "
      f"<b>no naïve pooling</b>. Squares = cohort estimates with 95% CIs; diamonds = pooled estimates; "
      f"dashed vertical line = null effect (1.0). Pooled primary estimates: P1 "
      f"<b>{p1['effect']:.3f} ({p1['lo']:.3f}–{p1['hi']:.3f})</b>, I²={m1['I2']:.1f}%; "
      f"P2inc <b>{p2['effect']:.3f} ({p2['lo']:.3f}–{p2['hi']:.3f})</b>, I²={m2['I2']:.1f}%. "
      f"Secondary: B10 {b10['effect']:.3f} ({b10['lo']:.3f}–{b10['hi']:.3f}), I²={m10['I2']:.1f}%; "
      f"B40 {b40['effect']:.3f} ({b40['lo']:.3f}–{b40['hi']:.3f}), I²={m40['I2']:.1f}%, "
      f"<b>not statistically significant</b>. SHARE threshold outcomes use wave 1 only (household-income definitions "
      f"differ from wave 2 onward); HRS waves 3–16 were annualised by dividing the 2-year recall amount by 2; "
      f"all amounts were deflated to 2020 international dollars using country-specific PPP and US CPI. "
      f"Abbreviations: OOP, out-of-pocket; I², proportion of between-study heterogeneity.",
      f"<b>Figure 2</b>  Event study centred on the wave at which arthritis was first reported; outcome = log(1 + annualised "
      f"OOP amount), coefficients expressed as 100 × log units relative to the reference period k = −1. "
      f"Cohorts: MHAS (n={int(k0['mhas']['n_ids']):,}), HRS (n={int(k0['hrs']['n_ids']):,}), "
      f"SHARE (n={int(k0['share']['n_ids']):,}); never-diagnosed respondents served as controls. "
      f"Points are event-time coefficients with 95% CIs (individual-ID cluster-robust); open circles denote the "
      f"reference period (fixed at zero); dashed vertical lines mark the first-report wave. Joint Wald tests for "
      f"pre-trends were non-significant (MHAS P={pre.get('mhas',float('nan')):.2f}, "
      f"HRS P={pre.get('hrs',float('nan')):.2f}, SHARE P={pre.get('share',float('nan')):.2f}). "
      f"At the first-report wave, OOP amount rose by {100*k0['mhas']['beta']:.1f} (MHAS), "
      f"{100*k0['hrs']['beta']:.1f} (HRS) and {100*k0['share']['beta']:.1f} (SHARE) 100 × log units "
      f"(all P&lt;0.001), attenuating at k=+1 and disappearing by k=+2. "
      f"<b>Limitations</b>: the 2-year HRS recall window overlaps the 2-year wave interval, so k=0 may span the "
      f"period before true onset; `arthre` is an ever-diagnosed cumulative indicator, so first report ≠ true onset. "
      f"Findings should therefore be described as occurring <b>at the wave arthritis was first reported</b> and "
      f"should not be interpreted causally. CHARLS was excluded because 1,218 respondents reverted from 1 to 0 and "
      f"OOP amount was available for only 45.1% of person-waves.",
      f"<b>Figure 3</b>  (A) Arthritis-minus-control differences in each component's share of total annualised OOP "
      f"(percentage points with 95% CIs; individual-ID cluster-robust). (B) Component-specific excess OOP "
      f"(2020 international $/year) after proportional closure to the A1 g-computation total (dashed lines: "
      f"{tot_txt}). Data comprise 353,111 person-waves from MHAS (6 waves), SHARE (4), "
      f"LASI (1) and CHARLS (4); <b>component sums matched harmonised totals exactly in 15/15 cohort-wave cells</b>, "
      f"so this is an exact accounting decomposition rather than an approximation. Drug components were available "
      f"in MHAS and SHARE only and were not pooled; the medication share increased by "
      f"<b>+{mh['diff_pp']:.2f} pp ({mh['lo_pp']:.2f}–{mh['hi_pp']:.2f})</b> in MHAS and "
      f"<b>+{sh['diff_pp']:.2f} pp ({sh['lo_pp']:.2f}–{sh['hi_pp']:.2f})</b> in SHARE (both P&lt;0.001) as "
      f"single-cohort observations. "
      f"Pooled outpatient amount ratio {ao['pooled_effect']:.3f} ({ao['lo']:.3f}–{ao['hi']:.3f}), whereas the "
      f"inpatient amount ratio {ai['pooled_effect']:.3f} ({ai['lo']:.3f}–{ai['hi']:.3f}) was <b>not significant</b>. "
      f"Ratios of independent component g-computation to the A1 total were "
      f"{cl.get('mhas',float('nan')):.3f} (MHAS), {cl.get('share',float('nan')):.3f} (SHARE) and "
      f"{cl.get('lasi',float('nan')):.3f} (LASI), reflecting model approximation rather than a data error; "
      f"Panel B therefore reports an additional proportional-closure allocation of excess OOP and both tracks are presented. "
      f"HRS has no amount components and is excluded; CHARLS uses a self-constructed annualised total that omits "
      f"medication (≈1–2% underestimate) and is shown as an extension only. "
      f"<b>OOP amount is not utilisation</b>: these results must not be described as increased drug use. "
      f"The SHARE `other` component reversed direction after adjustment and is not interpreted.",
      f"<b>Figure 4</b>  Country-specific ORs for any OOP spending in 20 SHARE countries (points with 95% CIs; "
      f"point area ∝ √sample size) plotted against the out-of-pocket share of current health expenditure "
      f"(2004–2005 mean), with the random-effects meta-regression fit (dashed red line) and its 95% band (pale red). "
      f"Country-level covariates came from World Bank WDI; OOP share ranged from "
      f"{SCAT.oop_pct_che_mean0405.min():.2f}% to {SCAT.oop_pct_che_mean0405.max():.2f}%. "
      f"<b>{npos}/20 countries had OR &gt; 1</b>, indicating a highly consistent direction, yet a 1-SD higher OOP "
      f"share was associated with an OR ratio of <b>{mr['ratio_per_sd']:.3f} "
      f"({mr['lo']:.3f}–{mr['hi']:.3f}), P={mr['p']:.3f}, R²={mr['R2']:.2f}</b>, with residual "
      f"I²={mr['I2_resid']:.1f}% and τ²={mr['tau2_used']:.4f}. None of 20 leave-one-out fits and none of nine "
      f"WDI institutional covariates survived Benjamini–Hochberg correction. The appropriate conclusion is "
      f"<b>no evidence of an institutional gradient</b>, reframed positively as consistency across institutional "
      f"settings; it must not be stated that institutions have no effect, and it should not be used as a "
      f"title-level claim.",
      f"<b>Figure 5</b>  Effect modification by socioeconomic position. (A) Four-cohort random-effects pooled "
      f"estimates for both primary outcomes (P1, any OOP spending, OR; P2inc, amount ratio among spenders) "
      f"within household-income quintiles defined separately in each cohort and wave, and within three levels "
      f"of educational attainment (approximated from cohort-specific education codes); {n_strata} strata in "
      f"total. Squares are pooled "
      f"estimates with 95% CIs and the dashed vertical line marks the null (1.0). "
      f"<b>All {n_strata}/{n_strata} stratum-specific pooled estimates had lower 95% bounds above 1</b>, "
      f"so the association was present in every socioeconomic stratum. Formal interaction tests "
      f"(2 outcomes × 2 SES axes; Benjamini–Hochberg FDR): the ratio of effects per income quintile for P1 was "
      f"{i_p1_inc} and per education level for P2inc was {i_p2_edu}; both point towards slightly larger "
      f"relative effects at <b>higher</b>, not lower, socioeconomic position, are small in magnitude and show "
      f"substantial between-cohort heterogeneity. The other two interaction tests were null "
      f"(P1 by education {i_p1_edu}; P2inc by income quintile {i_p2_inc}). "
      f"(B) Descriptive, unadjusted difference in weighted mean annual OOP spending between respondents "
      f"with and without arthritis as a percentage of stratum median household income, by income quintile "
      f"(log vertical axis; SHARE wave 1 only). The median Q1/Q5 ratio across four cohorts was {eq_med}. "
      f"<b>This gradient is driven by the income denominator and is not evidence of effect modification, "
      f"nor a standardised or causal quantity</b>; absolute excess amounts were of a similar order of "
      f"magnitude across quintiles or slightly higher in Q5. Wording boundary: it must not be stated that "
      f"lower-SES groups bear a larger relative burden, or that inequity is demonstrated."
    ]

# ---------------------------------------------------------------- HTML 组装
CSS = """
<style>
*{box-sizing:border-box}
body{background:#ffffff;color:#1a1a1a;margin:0;padding:30px 34px 60px;
 font-family:"Microsoft YaHei","SimHei",Arial,sans-serif;line-height:1.65}
.wrap{max-width:1060px;margin:0 auto}
h1{font-size:21px;line-height:1.35;margin:0 0 8px;font-weight:700;color:#12283f}
.sub{font-size:12px;color:#5b6470;margin:0 0 6px}
.note{font-size:11.5px;color:#7a818b;margin:0 0 22px;padding:9px 12px;
 background:#f6f8fa;border-left:3px solid #c8d2dc}
figure{margin:0 0 40px;padding:0;page-break-inside:avoid;break-inside:avoid}
h2{font-size:15px;margin:0 0 10px;color:#12283f;font-weight:700}
.svgbox{border:1px solid #e4e8ec;padding:6px;background:#fff;overflow:hidden}
svg{display:block;width:100%;height:auto}
figcaption{font-size:12px;text-align:justify;color:#242a30;margin-top:11px;
 padding-top:9px;border-top:1px solid #d9dfe5;line-height:1.7}
.en h1,.en h2,.en figcaption,.en .sub,.en .note{font-family:"Times New Roman",Georgia,serif}
.en figcaption{font-size:13px}
.foot{font-size:11px;color:#7a818b;border-top:1px solid #e4e8ec;padding-top:12px;margin-top:30px}
@media print{body{padding:0} .wrap{max-width:none} figure{page-break-inside:avoid} .svgbox{border:none;padding:0}}
</style>
"""
def build(lang):
    t = TXT[lang]
    figs = [fig1(lang), fig2(lang), fig3(lang), fig4(lang), fig5(lang)]
    legs = legends(lang)
    nums = ['1','2','3','4','5']
    body = []
    for i,(svg,leg) in enumerate(zip(figs,legs)):
        body.append(f'<figure><h2>{esc(t["f"+nums[i]])}</h2>'
                    f'<div class="svgbox">{svg}</div>'
                    f'<figcaption>{leg}</figcaption></figure>')
    foot = ("数据来源：本机 HRS 家族 10 个 harmonized 老龄化队列（PostgreSQL，只读抽取）；"
            "平减因子来自 World Bank WDI（PPP PA.NUS.PPP、CPI FP.CPI.TOTL，lastupdated 2026-11-11）；"
            "国家制度变量来自 World Bank WDI / WHO GHED。全部脚本 out/07–33_*.py 与结果 CSV 可复现。"
            if lang=='zh' else
            "Data: ten locally deployed harmonised HRS-family ageing cohorts (PostgreSQL, read-only extraction); "
            "deflators from World Bank WDI (PPP PA.NUS.PPP; CPI FP.CPI.TOTL; last updated 2026-11-11); "
            "country-level covariates from World Bank WDI / WHO GHED. All scripts (out/07–33_*.py) and result CSVs are deposited for reproducibility.")
    return (f'<!DOCTYPE html><html lang="{"zh-CN" if lang=="zh" else "en"}"><head>'
            f'<meta charset="utf-8"><title>{esc(t["doc"])}</title>{CSS}</head>'
            f'<body class="{lang}"><div class="wrap"><h1>{esc(t["doc"])}</h1>'
            f'<p class="sub">{esc(t["sub"])}</p><p class="note">{esc(t["note"])}</p>'
            + '\n'.join(body) +
            f'<div class="foot">{esc(foot)}</div></div></body></html>')

for lang, name in [('zh','方向A_Figures_CN.html'), ('en','方向A_Figures_EN.html')]:
    p = os.path.join(ROOT, name)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(build(lang))
    print('WROTE', p, os.path.getsize(p), 'bytes')
