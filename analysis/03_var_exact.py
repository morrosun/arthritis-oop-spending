# -*- coding: utf-8 -*-
"""精确变量核对：各库 OOPE 总量变量、风湿变量的波次覆盖、变量标签、非缺失行数、R 分析层是否含该列。只读。"""
import os, re, json, glob, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['charls', 'hrs', 'share', 'mhas', 'lasi', 'creles', 'elsa', 'clhls', 'klosa', 'elsa_raw']
RDATA_DIRS = [p for p in os.environ.get("OOPE_RDATA_DIRS", "").split(os.pathsep) if p]

lines = []
def log(s=''):
    print(s); lines.append(str(s))

pat_rheum = re.compile(r'^[rs]\d+(arthre|osteoe|rxarthr|rxosteo|arthr|osteo)$', re.I)
pat_oop_total = re.compile(r'oopmd', re.I)

report = {}
for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT column_name FROM information_schema.columns
                   WHERE table_schema='public'""")
    cols = sorted({r[0] for r in cur.fetchall()})

    oop = [c for c in cols if pat_oop_total.search(c)]
    oop_all = [c for c in cols if 'oop' in c.lower()]
    rhe = [c for c in cols if pat_rheum.match(c)]
    # 其它风湿相关词
    other = [c for c in cols if re.search(r'(rheum|gout|uric|osteo|arthri)', c, re.I)][:60]
    log(f"OOPE 总量变量(含 oopmd) n={len(oop)}: {', '.join(oop)}")
    log(f"含 oop 的变量 n={len(oop_all)}（前 60）: {', '.join(oop_all[:60])}")
    log(f"风湿 harmonized 变量 n={len(rhe)}: {', '.join(rhe)}")
    log(f"其它风湿词干命中 n={len(other)}: {', '.join(other)}")

    # 变量标签
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='public' AND (table_name ILIKE '%var_label%' OR table_name ILIKE '%variable_label%')""")
    ltabs = [r[0] for r in cur.fetchall()]
    labs = {}
    for t in ltabs:
        cur.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (t,))
        tcols = [r[0] for r in cur.fetchall()]
        if len(tcols) < 2:
            continue
        try:
            q = sql.SQL('SELECT * FROM public.{} WHERE {} ILIKE %s OR {} ILIKE %s LIMIT 60').format(
                sql.Identifier(t), sql.Identifier(tcols[0]), sql.Identifier(tcols[1]))
            cur.execute(q, ('%oopmd%', '%arthre%'))
            rows = cur.fetchall()
            for r in rows:
                labs[str(r[0])] = ' | '.join(str(x)[:180] for x in r[1:])
        except Exception:
            conn.rollback()
    if labs:
        log("  标签样例:")
        for k, v in list(labs.items())[:15]:
            log(f"    {k}: {v}")

    # 非缺失行数（对总量 OOPE 变量，按所在表分组，每库最多 10 个变量）
    counts = {}
    targets = oop[:10] or oop_all[:6]
    bytable = {}
    for c in targets:
        cur.execute("""SELECT table_name FROM information_schema.columns
                       WHERE table_schema='public' AND column_name=%s LIMIT 1""", (c,))
        r = cur.fetchone()
        if r:
            bytable.setdefault(r[0], []).append(c)
    for t, vcols in list(bytable.items())[:4]:
        try:
            sel = sql.SQL(', ').join(
                sql.SQL('count({}) AS {}').format(sql.Identifier(c), sql.Identifier('n_' + c)) for c in vcols[:5])
            q = sql.SQL('SELECT count(*) AS nrow, {} FROM public.{}').format(sel, sql.Identifier(t))
            cur.execute(q)
            row = cur.fetchone()
            counts[t] = {'nrow': row[0], 'vars': dict(zip(vcols[:5], row[1:]))}
            log(f"  非缺失 [{t}]: {counts[t]}")
        except Exception as e:
            conn.rollback()
            log(f"  非缺失统计失败 [{t}]: {str(e)[:120]}")
    report[db] = {'oop_total': oop, 'oop_all_n': len(oop_all), 'rheum': rhe,
                  'other_rheum': other, 'labels': labs, 'nonnull': counts}
    conn.close()

# R 分析层核对
log("\n########## R 分析层 (RData) ##########")
rres = {}
for d in RDATA_DIRS:
    for fp in sorted(glob.glob(os.path.join(d, '*.RData'))):
        key = os.path.basename(fp)
        try:
            import pyreadr
            obj = pyreadr.read_r(fp)
            df = list(obj.values())[0]
            cn = list(df.columns) if hasattr(df, 'columns') else []
            oopc = [c for c in cn if 'oop' in c.lower()]
            arc = [c for c in cn if re.search(r'(arth|rheum|osteo|gout|uric)', c, re.I)]
            log(f"{key}: dim={getattr(df, 'shape', '?')} | oop列={oopc[:20]} | 风湿列={arc[:20]}")
            rres[key] = {'shape': list(getattr(df, 'shape', [])), 'oop': oopc, 'rheum': arc}
        except Exception as e:
            log(f"{key}: 读取失败 {type(e).__name__} {str(e)[:100]}")
            rres[key] = {'error': str(e)[:200]}

with open(os.path.join(OUT, '03_var_exact.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '03_var_exact.json'), 'w', encoding='utf-8') as f:
    json.dump({'pg': report, 'rdata': rres}, f, ensure_ascii=False, indent=1)
print("\nDONE -> 03_var_exact.txt / .json")
