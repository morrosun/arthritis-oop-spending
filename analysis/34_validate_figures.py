# -*- coding: utf-8 -*-
"""图表交付校验：SVG 合法性、元素越界、中英文关键数字一致性、与结果 CSV 对账。
输出：34_figure_validation.txt
"""
import os, re, html, xml.etree.ElementTree as ET
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
FILES = {'zh': os.path.join(OUT,'Figures_CN.html'),
         'en': os.path.join(OUT,'Figures_EN.html')}
lines = []
def log(s=''): print(s, flush=True); lines.append(str(s))

log("图表交付校验｜2026-11-13")
alltxt = {}
for lang, p in FILES.items():
    h = open(p, encoding='utf-8').read()
    svgs = re.findall(r'<svg .*?</svg>', h, re.S)
    caps = re.findall(r'<figcaption>(.*?)</figcaption>', h, re.S)
    log(f"\n## {lang.upper()}  {os.path.basename(p)}  {os.path.getsize(p):,} bytes")
    log(f"  SVG 数={len(svgs)}  图注数={len(caps)}  <figure> 数={h.count('<figure>')}")
    assert len(svgs)==5 and len(caps)==5 and h.count('<figure>')==5, \
        'expected 5 figures (Fig1–Fig5), got %d/%d/%d' % (len(svgs), len(caps), h.count('<figure>'))
    for i, sv in enumerate(svgs, 1):
        root = ET.fromstring(sv)
        vb = [float(x) for x in root.attrib['viewBox'].split()]
        W, H = vb[2], vb[3]
        texts = root.findall('.//{http://www.w3.org/2000/svg}text')
        bad = []
        for e in texts:
            x, y = float(e.attrib['x']), float(e.attrib['y'])
            if not (-4 <= x <= W+4 and -4 <= y <= H+4): bad.append((x, y, (e.text or '')[:28]))
        n_shape = (len(root.findall('.//{http://www.w3.org/2000/svg}line')) +
                   len(root.findall('.//{http://www.w3.org/2000/svg}rect')) +
                   len(root.findall('.//{http://www.w3.org/2000/svg}circle')) +
                   len(root.findall('.//{http://www.w3.org/2000/svg}polygon')) +
                   len(root.findall('.//{http://www.w3.org/2000/svg}polyline')))
        log(f"  Fig{i}: viewBox {W:.0f}x{H:.0f}  text={len(texts)}  shape={n_shape}  "
            f"越界文本={len(bad)}  XML=OK")
        for b in bad[:5]: log(f"    越界: {b}")
    alltxt[lang] = h

# 关键数字：中英文两版必须一致（从图注里抽取所有带括号的 95% CI）
log("\n## 中英文图注数字一致性")
pat = re.compile(r'\d+\.\d{3}\s*[–-]\s*\d+\.\d{3}')
a = sorted(pat.findall(' '.join(re.findall(r'<figcaption>(.*?)</figcaption>',
                                          alltxt['zh'], re.S))))
b = sorted(pat.findall(' '.join(re.findall(r'<figcaption>(.*?)</figcaption>',
                                          alltxt['en'], re.S))))
log(f"  中文版 3 位小数 CI 数={len(a)}  英文版={len(b)}  完全相同={a==b}")
if a != b:
    log("  仅中文:", [x for x in a if x not in b][:10])
    log("  仅英文:", [x for x in b if x not in a][:10])

# 与结果 CSV 对账（图内/图注出现的主结局合并值）
log("\n## 与结果 CSV 对账")
F = pd.read_csv(os.path.join(OUT,'22_1a_forest.csv'))
S = pd.read_csv(os.path.join(OUT,'22_1a_sensitivity_table.csv'))
G = pd.read_csv(os.path.join(OUT,'22_1a_gcomp.csv'))
# 合并值以 6 位小数源为准；F 已先舍到 4 位，再截 3 位会二次舍入（B40 下限 0.862482→0.863）
M6 = (pd.read_csv(os.path.join(OUT,'21_a1_revised_meta.csv'))
      .query("set == 'main_revised'").set_index('outcome'))
checks = []
for oc in ['P1_any_oop','P2inc_amount_log_adj_income','B10_oop_ge10pct_income',
           'B40_oop_ge40pct_income']:
    r = F[(F.outcome==oc)&(F.db=='POOLED (RE)')].iloc[0]
    m = S[(S.set=='main_revised')&(S.outcome==oc)].iloc[0]
    if oc in M6.index:
        eff, lo, hi = (float(M6.loc[oc,'pooled_effect']), float(M6.loc[oc,'lo']),
                       float(M6.loc[oc,'hi']))
    else:
        eff, lo, hi = float(r['effect']), float(r['lo']), float(r['hi'])
    for v in [f"{eff:.3f}", f"{lo:.3f}", f"{hi:.3f}", f"{m['I2']:.1f}%"]:
        checks.append((oc, v, all(v in alltxt[l] for l in ('zh','en'))))
for db, v in G[['db','attributable_oop_2020intl']].itertuples(index=False):
    if db == 'hrs':
        log(f"  {'gcomp_hrs':<34s} {float(v):<10.1f} N/A（HRS 无金额分项，不进 Fig3 Panel B）")
        continue
    checks.append(('gcomp_'+db, f"{float(v):.1f}", all(f"{float(v):.1f}" in alltxt[l] for l in ('zh','en'))))
for oc,v,ok in checks: log(f"  {oc:<34s} {v:<10s} 两版均出现={ok}")
log(f"  通过 {sum(1 for _,_,ok in checks if ok)}/{len(checks)}（HRS 一项不适用，已单列）")

# Figure 5：SES 分层结果与 41_ses_*.csv 逐项对账
log("\n## Figure 5 / SES 结果与 CSV 对账")
SEST = pd.read_csv(os.path.join(OUT,'41_ses_tests.csv')).set_index('test')
SESF = pd.read_csv(os.path.join(OUT,'41_ses_figure.csv'))
SESR = pd.read_csv(os.path.join(OUT,'41_ses_equity_ratio.csv'))
ses_checks = []
for k in ['T_P1_income','T_P1_education','T_P2inc_income','T_P2inc_education']:
    r = SEST.loc[k]
    ses_checks.append((k, '%.3f (%.3f–%.3f)' % (r.estimate, r.lo, r.hi)))
r = SEST.loc['T_equity_ratio']
ses_checks.append(('T_equity_ratio', '%.1f (%.1f–%.1f)' % (r.estimate, r.lo, r.hi)))
for _, r in SESF.iterrows():
    ses_checks.append(('stratum %s/%s/%s' % (r.outcome, r.axis, r.stratum),
                       '%.3f (%.3f–%.3f)' % (r.effect, r.lo, r.hi)))
ses_fail = [(k, v) for k, v in ses_checks
            if not all(v in alltxt[l] for l in ('zh','en'))]
for k, v in ses_checks:
    log(f"  {k[:44]:<44s} {v:<24s} 两版均出现={all(v in alltxt[l] for l in ('zh','en'))}")
log(f"  SES 数字对账 {len(ses_checks)-len(ses_fail)}/{len(ses_checks)}；"
    f"表中分层行 {len(SESF)} 条、Q1/Q5 描述性比 {len(SESR)} 库")
log(f"  Figure 5 段落存在: "
    f"{all(('Figure 5' in alltxt['en'] or '图 5' in alltxt[l]) for l in ('zh','en'))}")

# 术语：全稿统一 excess，不得再以肯定语境使用 attributable / 归因
log("\n## excess 术语统一（attributable/归因 只允许出现在「不得使用」的否定语境）")
TERM_NEG = ['never', 'not ', 'do not', 'must not', 'rather than',
            '不用', '不再用', '不得', '而非', '统一用']
for bad in ['attributable', '归因']:
    bad_hits = 0
    for l in ('zh', 'en'):
        for m in re.finditer(re.escape(bad), alltxt[l], re.I):
            ctx = alltxt[l][max(0, m.start()-60):m.start()].lower()
            if not any(k in ctx for k in TERM_NEG):
                bad_hits += 1
                log(f"    BAD! {l} 肯定语境: ...{html.unescape(alltxt[l][max(0,m.start()-70):m.end()+40])}...")
    log(f"  {'OK ' if bad_hits == 0 else 'BAD!'}  {bad}: 肯定语境残留 {bad_hits} 处")
log("  图注与图内正式表述一律为 excess / 超额自付。")

# 措辞红线（英文版）
log("\n## 英文版措辞红线")
red = ['first multi-cohort harmonised estimate', 'no evidence of an institutional gradient',
       'income-based financial burden', 'not WHO-style catastrophic health expenditure',
       'no naïve pooling', 'should not be interpreted causally']
for r in red: log(f"  {'OK ' if r in alltxt['en'] else 'MISS'}  {r}")
log("  说明：以下禁用语应在图注中仅以「不得使用」的否定语境出现（作为红线提示）。")
NEG = ['must not', 'never', 'not be', 'cannot', 'should not', 'nor ']
for bad in ['institutions have no effect','increased drug use','WHO-style CHE is defined',
            'first study of arthritis out-of-pocket']:
    hits = list(re.finditer(re.escape(bad), alltxt['en'], re.I))
    if not hits:
        log(f"  OK    未出现: {bad}")
        continue
    ctx_ok = []
    for m in hits:
        ctx = alltxt['en'][max(0,m.start()-90):m.start()].lower()
        ctx_ok.append(any(k in ctx for k in NEG))
    good = all(ctx_ok)
    log(f"  {'OK ' if good else 'BAD!'}  仅出现于否定语境 {sum(ctx_ok)}/{len(hits)}: {bad}")
    if not good:
        for m, g in zip(hits, ctx_ok):
            if not g: log(f"      违规语境: ...{html.unescape(alltxt['en'][max(0,m.start()-70):m.end()+40])}...")

with open(os.path.join(OUT,'34_figure_validation.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\nWROTE 34_figure_validation.txt')
