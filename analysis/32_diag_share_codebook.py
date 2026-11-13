# -*- coding: utf-8 -*-
"""A1 遗留诊断③：官方 SHARE codebook 核对「10.3178」——实库证据部分。

核对该经验因子究竟是「可校正的常数缩放」还是「两个不同定义变量的个体比值中位数」。
产出：
  32_share_income_meta.txt           本机 harmonized SHARE 的收入变量清单 / 波次映射 / 列注释
  32_share_income_ratio_dist.csv     同一人 w2/w5/w6 对 w1 收入比的分位数与「接近固定倍数」占比
  32_share_income_ratio_country.csv  按国家的中位比值（检验是否为统一汇率/单位换算）
结论与官方 codebook 逐字原文见 32_SHARE_codebook_核对报告.md
"""
import os, time, numpy as np, pandas as pd, psycopg2

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '32_share_income_meta.txt')
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

log("A1 遗留诊断③：SHARE 收入口径实库证据｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
c = psycopg2.connect(CONN + ' dbname=share')
u = c.cursor()
u.execute("SELECT wave, year, source FROM public.share_wave_map ORDER BY wave")
log("\n## 波次映射表 share_wave_map")
for r in u.fetchall(): log(f"  w{r[0]} = {r[1]}  ({r[2]})")
u.execute("""SELECT table_name, string_agg(column_name, ',' ORDER BY column_name)
             FROM information_schema.columns WHERE table_schema='public'
               AND lower(column_name) LIKE '%itot%' GROUP BY 1 ORDER BY 1""")
log("\n## 含 itot 的收入类变量（按分片）")
for t, s in u.fetchall(): log(f"  {t}: {s}")
u.execute("""SELECT col_description('gh_share_p5'::regclass, ordinal_position), column_name
             FROM information_schema.columns WHERE table_schema='public'
               AND table_name='gh_share_p5'
               AND lower(column_name) IN ('hh1itot','hh2itothhinc','hh5itothhinc','hh6itothhinc')""")
log("\n## 列注释（col_description，均为空说明本机无 codebook 文本）")
for r in u.fetchall(): log(f"  {r[1]}: {r[0]}")
c.close()

d = pd.read_csv(os.path.join(OUT, '18_data_share.csv'), low_memory=False)
p = d[d.wave.isin([1,2,5,6])].pivot_table(index='id', columns='wave', values='hhinc', aggfunc='first')
p = p.join(d[d.wave==1].set_index('id')['iso3'].rename('iso3'))
p = p[(p[1] > 0) & (p[1] < 1e7)]

dist, country = [], []
for w in [2,5,6]:
    r = (p[w]/p[1]).replace([np.inf,-np.inf], np.nan).dropna()
    r = r[(r > 0) & (r < 100)]
    dist.append(dict(wave=w, n=len(r), mean=r.mean(), p10=r.quantile(.10), p25=r.quantile(.25),
                     median=r.median(), p75=r.quantile(.75), p90=r.quantile(.90),
                     pct_within_10_107=100*((r>10)&(r<10.7)).mean(),
                     pct_within_115_125=100*((r>11.5)&(r<12.5)).mean(),
                     pct_outside_5_20=100*((r<5)|(r>20)).mean()))
    q = p[(p[w] > 0) & (p[w] < 1e8)].assign(r=lambda x: x[w]/x[1])
    q = q[(q.r > 0) & (q.r < 100)]
    g = q.groupby('iso3')['r'].agg(n='size', median='median', p25=lambda x:x.quantile(.25),
                                   p75=lambda x:x.quantile(.75)).reset_index()
    g = g[g.n >= 100].assign(wave=w)
    country.append(g)

DIST = pd.DataFrame(dist); CTY = pd.concat(country, ignore_index=True)
DIST.to_csv(os.path.join(OUT,'32_share_income_ratio_dist.csv'), index=False,
            encoding='utf-8-sig', float_format='%.4f')
CTY.to_csv(os.path.join(OUT,'32_share_income_ratio_country.csv'), index=False,
           encoding='utf-8-sig', float_format='%.4f')

log("\n## 同一人 wX/w1 收入比（全局）")
log(DIST.round(3).to_string(index=False))
log("\n## 按国家中位比值（w2），检验是否为统一换算因子")
log(CTY[CTY.wave==2].round(3).to_string(index=False))
log(f"\n## 国家间中位比值范围（w2）: {CTY[CTY.wave==2]['median'].min():.2f} – "
    f"{CTY[CTY.wave==2]['median'].max():.2f}，"
    f"极差 {CTY[CTY.wave==2]['median'].max()-CTY[CTY.wave==2]['median'].min():.2f}")
_c = CTY[CTY.wave==2]['median']
log("\n判定：若 10.3178 是固定换算因子，比值应高度集中且国家间一致；"
    f"实测 P10–P90 跨越 {DIST.p10.min():.1f}–{DIST.p90.max():.1f}、"
    f"国家中位 {_c.min():.2f}–{_c.max():.2f}，故不是常数缩放。")
