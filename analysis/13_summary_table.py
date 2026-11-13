# -*- coding: utf-8 -*-
"""汇总 11/12 的结果为 Table 1（Markdown + CSV）与关键汇总数字。
纯本地读取已落盘 json/csv，不连数据库。"""
import os, json, csv

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
with open(os.path.join(OUT, '11_feasibility_main.json'), encoding='utf-8') as f:
    D11 = json.load(f)
with open(os.path.join(OUT, '12_components_charls.json'), encoding='utf-8') as f:
    D12 = json.load(f)
rows = D11['rows']

MAIN = ['mhas', 'hrs', 'share', 'lasi']
EXCLUDE = {('share', 7), ('hrs', 2), ('creles', 1), ('creles', 2), ('creles', 3),
           ('creles', 4), ('creles', 5)}

lines = []
def log(s=''):
    print(s); lines.append(str(s))

def f0(x): return '—' if x is None else f'{x:,.0f}'
def f1(x): return '—' if x is None else f'{x:.1f}'
def f2(x): return '—' if x is None else f'{x:.2f}'

log("# 方向 A 可行性描述表（Table 1 草稿）")
log("")
log("金额单位：各库本币名义值，已统一年化（HRS w3–w16 原为 2 年口径，除以 2；CRELES 原为 3 个月，乘 4）。")
log("剔除了 ≥999996 的哨兵值与负值。关节炎 = `r{w}arthre` = 1（自报 ever-diagnosed，仅受访者本人）。")
log("所有组间差异为**未校正的描述性差异**，不含任何推断统计。")
log("")

# 逐库逐波表
log("## 1. 逐库逐波自付支出分布与关节炎交叉样本量")
log("")
log("| 库 | 波(年) | 年化因子 | 有效 N | 零值% | 中位 | P90 | P95 | P99 | 插补% | 关节炎+ N | 对照 N | 有效样本内患病率% | 有支出率 关节炎/对照 % | 有支出者中位 关节炎/对照 | 中位比 |")
log("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for db in MAIN:
    for r in [x for x in rows if x['db'] == db]:
        w = int(r['wave'])
        mark = ' ⚠️' if (db, w) in EXCLUDE else ''
        log(f"| {db.upper()} w{w}{mark} | {int(r['year'])} | {r['divisor']:.2f} | {f0(r['n_valid'])} | "
            f"{f1(r['zero_pct'])} | {f0(r['p50'])} | {f0(r['p90'])} | {f0(r['p95'])} | {f0(r['p99'])} | "
            f"{f1(r['imputed_pct'])} | {f0(r['n_arth1'])} | {f0(r['n_arth0'])} | "
            f"{f1(r['arth_prevalence_pct'])} | {f1(r['posrate_a1_pct'])} / {f1(r['posrate_a0_pct'])} | "
            f"{f0(r['p50_a1pos'])} / {f0(r['p50_a0pos'])} | {f2(r['median_ratio_a1_a0'])} |")
log("")
log("⚠️ = 建议排除出主分析（见 §4）。CRELES 5 波另列于 §3，仅作敏感性。")
log("")

# 汇总
log("## 2. 汇总样本量")
log("")
log("| 库 | 波数 | 有效人波 | 关节炎+ 人波 | 有支出者中位比范围 | 有支出率差范围(pp) |")
log("|---|---:|---:|---:|---|---|")
tot_all = tot_sel = art_all = art_sel = 0
summary = {}
for db in MAIN:
    rr = [x for x in rows if x['db'] == db]
    sel = [x for x in rr if (db, int(x['wave'])) not in EXCLUDE]
    n_all = sum(x['n_valid'] for x in rr); n_sel = sum(x['n_valid'] for x in sel)
    a_all = sum(x['n_arth1'] for x in rr); a_sel = sum(x['n_arth1'] for x in sel)
    ratios = [x['median_ratio_a1_a0'] for x in rr if x['median_ratio_a1_a0']]
    diffs = [x['posrate_a1_pct'] - x['posrate_a0_pct'] for x in rr
             if x['posrate_a1_pct'] is not None and x['posrate_a0_pct'] is not None]
    summary[db] = dict(waves=len(rr), waves_selected=len(sel), n_all=n_all, n_selected=n_sel,
                       arth_all=a_all, arth_selected=a_sel,
                       ratio_range=[min(ratios), max(ratios)],
                       posrate_diff_range=[min(diffs), max(diffs)])
    log(f"| {db.upper()} | {len(rr)} ({len(sel)}) | {n_all:,.0f} ({n_sel:,.0f}) | "
        f"{a_all:,.0f} ({a_sel:,.0f}) | {min(ratios):.2f}–{max(ratios):.2f} | "
        f"{min(diffs):+.1f}–{max(diffs):+.1f} |")
    tot_all += n_all; tot_sel += n_sel; art_all += a_all; art_sel += a_sel
log(f"| **四库合计** | **{sum(len([x for x in rows if x['db']==d]) for d in MAIN)} "
    f"({sum(summary[d]['waves_selected'] for d in MAIN)})** | **{tot_all:,.0f} ({tot_sel:,.0f})** | "
    f"**{art_all:,.0f} ({art_sel:,.0f})** | **1.14–1.51** | **+1.7–+15.8** |")
log("")
log("括号内为建议排除 SHARE w7、HRS w2 后的主分析样本。CRELES 未计入。")
log("")

# CRELES
log("## 3. CRELES（仅作敏感性，不进主分析）")
log("")
log("| 波(年) | 年化因子 | 有效 N | 零值% | 中位 | P95 | 患病率% | 中位比 |")
log("|---|---:|---:|---:|---:|---:|---:|---:|")
for r in [x for x in rows if x['db'] == 'creles']:
    log(f"| w{int(r['wave'])} ({int(r['year'])}) | {r['divisor']:.2f} | {f0(r['n_valid'])} | "
        f"{f1(r['zero_pct'])} | {f0(r['p50'])} | {f0(r['p95'])} | "
        f"{f1(r['arth_prevalence_pct'])} | {f2(r['median_ratio_a1_a0'])} |")
log("")
log("CRELES 分项加总/总额的中位比为 12–18、corr 仅 0.01–0.45（3 个月总额 vs 年度住院 + 月度专科，口径不相容），")
log("且 86–91% 为零值、双队列样本不重叠 → **排除出金额主分析**。")
log("")

# 分项一致性
log("## 4. 支出分项：可得性与加总一致性（A2 的可行性证据）")
log("")
log("| 库 | 波 | 分项（覆盖率） | 分项和/总额 中位比 | corr | 精确相等 | 判定 |")
log("|---|---|---|---:|---:|---:|---|")
for db in MAIN:
    if db == 'charls' or db not in D12['components']: continue
    for w, wd in sorted(D12['components'][db]['waves'].items(), key=lambda kv: int(kv[0])):
        cs = wd.get('_consistency')
        parts = ', '.join(f"{p} {v['coverage_pct']}%" for p, v in wd.items() if not p.startswith('_'))
        if cs:
            log(f"| {db.upper()} w{w} | {w} | {parts} | {f2(cs['median_sum_over_total'])} | "
                f"{cs['corr']:.4f} | {cs['n_exact_match']:,}/{cs['n']:,} | ✅ 精确分解 |")
log("")
log("**HRS 无任何支出分项变量**（RAND 只给总额 `r{w}oopmd`）→ A2 结构分解只能基于 MHAS / SHARE / LASI 三库")
log("（CHARLS 可用自建分项，但见 §5 的口径限制）。")
log("")

# CHARLS
log("## 5. CHARLS 自建年化总额与 EOL 公式对账")
log("")
log("在世波次自建公式：`r{w}oopdoc1m × 12 + r{w}oophos1y + r{w}oopden1y`（w1/w4 无牙科项）。")
log("")
log("| 波 | 有效 N | 分量齐全 N | 零值% | 中位 | P90 | P95 | P99 | 关节炎+ N | 有支出率 关节炎/对照 % | 有支出者中位 关节炎/对照 |")
log("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for w in [1,2,3,4]:
    d = D12['charls'].get(f'w{w}_derived')
    if not d: continue
    p1 = 100*d['n_a1pos']/d['n_a1'] if d['n_a1'] else None
    p0 = 100*d['n_a0pos']/d['n_a0'] if d['n_a0'] else None
    log(f"| w{w} | {f0(d['n'])} | {f0(d['n_complete'])} | {f1(100*d['n_zero']/d['n']) if d['n'] else '—'} | "
        f"{f0(d['p50'])} | {f0(d['p90'])} | {f0(d['p95'])} | {f0(d['p99'])} | {f0(d['n_a1'])} | "
        f"{f1(p1)} / {f1(p0)} | {f0(d['p50_a1pos'])} / {f0(d['p50_a0pos'])} |")
log("")
log("EOL 表（`harm_h_charls_eol_a`，408 行）用同一公式反推 harmonized 总额 `raxoopmd1y_c`：")
log("")
log("| 公式 | n | corr | 精确相等 | 中位(公式/总额) | 均值 总额 / 公式 |")
log("|---|---:|---:|---:|---:|---:|")
for k, v in D12['charls'].items():
    if not k.startswith('eol_formula_'): continue
    log(f"| {k.replace('eol_formula_','')} | {v['n']} | {v['corr']:.4f} | {v['n_exact']} | "
        f"{f2(v['median_ratio_s_over_t'])} | {f0(v['mean_total'])} / {f0(v['mean_formula'])} |")
log("")
log("**结论**：harmonized 总额 = 门诊×12 + 住院 + 牙科 + **药费**；加入药费后 corr 0.9999、中位比 1.000。")
log("但**在世波次没有逐波药费变量**（`oopdrug1y` 只存在于 EOL 跨波汇总层）→ 自建年化总额系统性漏药费，")
log("EOL 对账给出偏差约 1–2%（均值 38,501 vs 38,027）。因此 CHARLS 只作扩展/敏感性库，")
log("且自建口径必须在方法里明确声明与 harmonized 口径不等价。")
log("")

# 落盘
with open(os.path.join(OUT, '13_summary_table.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '13_summary.json'), 'w', encoding='utf-8') as f:
    json.dump({'per_cohort': summary,
               'four_cohort_total': {'n_all': tot_all, 'n_selected': tot_sel,
                                     'arthritis_all': art_all, 'arthritis_selected': art_sel},
               'flag_distributions': D11['flag_distributions']}, f, ensure_ascii=False, indent=1)
log("DONE -> 13_summary_table.md / 13_summary.json")
print('\n'.join(lines[-8:]))
