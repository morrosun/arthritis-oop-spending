# -*- coding: utf-8 -*-
"""点查『因费用停药/放弃就医/未满足医疗需要』相关变量：用于验证把 OOPE 当暴露的反向设计可行性。只读。"""
import os, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['charls', 'hrs', 'share', 'mhas', 'lasi']   # cohorts carried forward in the paper (see README)
PATTERNS = ['%afford%', '%forgo%', '%forgone%', '%cost-related%', '%due to cost%',
            '%because of%cost%', '%could not%pay%', '%no money%', '%unmet need%',
            '%discontinu%', '%skip%med%', '%stopped%med%', '%not take%med%',
            '%postpone%', '%delay%care%', '%forego%']
COLREG = ('afford', 'forgo', 'crn', 'nonadh', 'unmet', 'skipmed', 'stopmed', 'discont', 'delaycare')

lines = []
def log(s=''):
    print(s); lines.append(str(s))

res = {}
for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT column_name FROM information_schema.columns WHERE table_schema='public'""")
    cols = sorted({r[0] for r in cur.fetchall()})
    colhit = [c for c in cols if any(k in c.lower() for k in COLREG)]
    log(f"列名命中 n={len(colhit)}: {', '.join(colhit[:60])}")

    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema='public'
                   AND (table_name ILIKE '%var_label%' OR table_name ILIKE '%variable_label%'
                        OR table_name ILIKE '%value_label%')""")
    tabs = [r[0] for r in cur.fetchall()]
    hits = []
    for t in tabs:
        cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (t,))
        tc = cur.fetchall()
        textcols = [c for c, d in tc if d in ('text', 'character varying', 'character')]
        if not textcols:
            continue
        for pat in PATTERNS:
            try:
                q = sql.SQL('SELECT * FROM public.{} WHERE ').format(sql.Identifier(t)) + \
                    sql.SQL(' OR ').join(sql.SQL('{} ILIKE %s').format(sql.Identifier(c)) for c in textcols) + \
                    sql.SQL(' LIMIT 8')
                cur.execute(q, tuple([pat] * len(textcols)))
                for r in cur.fetchall():
                    hits.append((t, pat, [str(x)[:200] for x in r]))
            except Exception:
                conn.rollback()
    seen = set(); uniq = []
    for h in hits:
        key = tuple(h[2])
        if key not in seen:
            seen.add(key); uniq.append(h)
    log(f"标签语义命中(去重) n={len(uniq)}")
    for t, pat, vals in uniq[:35]:
        log(f"    [{pat}] {t}: {vals}")
    res[db] = {'col_hits': colhit, 'label_hits': uniq[:60]}
    conn.close()

with open(os.path.join(OUT, '05_behavior_vars.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '05_behavior_vars.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("\nDONE -> 05_behavior_vars.txt / .json")
