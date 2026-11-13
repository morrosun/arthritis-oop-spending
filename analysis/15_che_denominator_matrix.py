# -*- coding: utf-8 -*-
"""CHE 分母（家庭消费 ctot / 家庭收入 itot）逐库逐波可得性与量级核验。
只读。结果落盘 15_che_denominator_matrix.txt / .json。"""
import os, re, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['mhas', 'hrs', 'share', 'lasi', 'charls']

lines = []
def log(s=''):
    print(s); lines.append(str(s))
report = {}

for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='180s'")
    cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                   WHERE table_schema='public'
                     AND (column_name ~* '^(hh|h)[0-9]+(ctot|itot)'
                          OR column_name ~* '^(hh|h)[0-9]+.*(cons|exp)')""")
    loc = {}
    for t, c in cur.fetchall():
        loc.setdefault(c.lower(), t)
    cons = sorted([c for c in loc if 'ctot' in c or 'cons' in c or 'exp' in c])
    inc = sorted([c for c in loc if 'itot' in c])
    log(f"  消费类候选 ({len(cons)}): {', '.join(cons[:30])}")
    log(f"  收入类候选 ({len(inc)}): {', '.join(inc[:30])}")
    dbres = {'consumption': {}, 'income': {}}
    for group, vs in [('consumption', cons[:24]), ('income', inc[:24])]:
        for v in vs:
            t = loc[v]
            try:
                cur.execute(sql.SQL("""SELECT count({c}),
                        count(*) FILTER (WHERE {c} > 0),
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY {c}) FILTER (WHERE {c} > 0),
                        min({c})::float8, max({c})::float8
                        FROM public.{t}""").format(c=sql.Identifier(v), t=sql.Identifier(t)))
                n, npos, med, mn, mx = cur.fetchone()
                dbres[group][v] = {'table': t, 'nonnull': n, 'positive': npos,
                                   'median_positive': float(med) if med is not None else None,
                                   'min': mn, 'max': mx}
                log(f"    {v:<20} [{t}] 非空={n:>7,} 正={npos:>7,} 中位(正)={dbres[group][v]['median_positive']} "
                    f"范围=[{mn}, {mx}]")
            except Exception as e:
                conn.rollback(); log(f"    {v}: 失败 {str(e)[:110]}")
    report[db] = dbres
    conn.close()

with open(os.path.join(OUT, '15_che_denominator_matrix.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '15_che_denominator_matrix.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 15_che_denominator_matrix.txt / .json")
