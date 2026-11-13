# -*- coding: utf-8 -*-
"""逐波确认 HRS oopmd 的时间窗（12 个月 vs 2 年）与 flag 编码，以及各库分项变量清单。
只读。落盘 10_probe_hrs_window.txt / .json。"""
import os, re, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))

lines = []
def log(s=''):
    print(s); lines.append(str(s))

report = {}

# ---------- HRS 时间窗标签 ----------
log("########## HRS: r/s{w}oopmd 逐波时间窗 ##########")
conn = psycopg2.connect(CONN + " dbname=hrs")
cur = conn.cursor()
cur.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name='hrs_variable_labels' ORDER BY ordinal_position""")
lc = [r[0] for r in cur.fetchall()]
log(f"hrs_variable_labels 列: {lc}")
varcol = next((c for c in lc if 'var' in c.lower() or c.lower() in ('name','column_name')), lc[1] if len(lc)>1 else lc[0])
labcol = next((c for c in lc if 'lab' in c.lower() or 'desc' in c.lower()), lc[-1])
q = sql.SQL('SELECT {v}, {l} FROM public.hrs_variable_labels WHERE {v} ILIKE %s ORDER BY 1').format(
    v=sql.Identifier(varcol), l=sql.Identifier(labcol))
cur.execute(q, ('%oopmd%',))
rows = cur.fetchall()
hrs_lab = {}
for v, l in rows:
    v, l = str(v), str(l)
    if re.match(r'^[rs]\d+oopmd[fo]?$', v, re.I) or v in ('h2oopmd','reoopmd'):
        hrs_lab[v] = l
        win = '2yr' if re.search(r'2\s*(yrs|years)', l, re.I) else ('12mo' if re.search(r'12\s*(mos|months)', l, re.I) else '?')
        log(f"  {v:<16} [{win}] {l[:110]}")
report['hrs_labels'] = hrs_lab
# 单独汇总 r 系列各波窗口
log("\n  --- r 系列（受访者本人）逐波窗口汇总 ---")
rwin = {}
for w in range(1, 17):
    v = f'r{w}oopmd'
    l = hrs_lab.get(v, '')
    win = '2yr' if re.search(r'2\s*(yrs|years)', l, re.I) else ('12mo' if re.search(r'12\s*(mos|months)', l, re.I) else 'NA')
    rwin[w] = {'label': l, 'window': win, 'annual_divisor': 2.0 if win == '2yr' else (1.0 if win == '12mo' else None)}
    log(f"    w{w:<2} {win:<5} divisor={rwin[w]['annual_divisor']}  {l[:90]}")
report['hrs_r_window'] = rwin
conn.close()

# ---------- 各库分项变量清单 ----------
log("\n########## 各库支出分项变量（r 系列，按波） ##########")
PAT = re.compile(r'^r(\d+)oop(?!md)([a-z0-9_]*)$', re.I)
for db, key in [('mhas','rahhidnp'), ('share','mergeid'), ('lasi','prim_key'),
                ('charls','id'), ('creles','idsujeto'), ('hrs','hhidpn')]:
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND column_name LIKE 'r%oop%'""")
    cols = sorted({r[0].lower() for r in cur.fetchall()})
    stems = {}
    for c in cols:
        m = PAT.match(c)
        if not m: continue
        w, rest = int(m.group(1)), m.group(2)
        # 去掉 f 标记后缀的干扰：仅保留非 flag 项
        if rest.endswith('f1y') or rest.endswith('f1m') or rest.endswith('fv3m') or rest.endswith('f'):
            continue
        stems.setdefault(rest, []).append(w)
    report[f'{db}_components'] = {k: sorted(v) for k, v in stems.items()}
    log(f"  {db}: " + ', '.join(f"{k}[w{','.join(map(str,v))}]" for k, v in sorted(stems.items())))
    conn.close()

with open(os.path.join(OUT, '10_probe_hrs_window.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '10_probe_hrs_window.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 10_probe_hrs_window.txt / .json")
