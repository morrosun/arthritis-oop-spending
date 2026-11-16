# -*- coding: utf-8 -*-
"""探测各库分片表结构：表清单、行数、ID 列、目标变量所在分片。
只读，不修改任何数据库。结果落盘 07_probe_structure.txt / .json。"""
import os, re, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['mhas', 'hrs', 'share', 'lasi', 'charls']   # cohorts carried forward in the paper (see README)

# 关注变量正则
PAT_TOTAL = re.compile(r'^[rs]\d+oopmd(1y(_l|_m)?|v3m)?$|^h2oopmd$|^reoopmd$|^r\d+oopmd$|^raxoopmd1y_c$', re.I)
PAT_ARTH = re.compile(r'^[rs]\d+arthre$', re.I)
PAT_COMP = re.compile(r'^[rs]\d+oop(doc|hos|drug|den|osrg|fhho|supl|hcn?h|spc|oth)', re.I)
PAT_FLAG = re.compile(r'^[rs]\d+oopmd.*f', re.I)
PAT_ID = re.compile(r'^(id|.*id.*|hhidpn|mergeid|pid|puid|raid| respondent|household)', re.I)

lines = []
def log(s=''):
    print(s); lines.append(str(s))

report = {}
for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""")
    tabs = [r[0] for r in cur.fetchall()]
    log(f"public 表 n={len(tabs)}: {', '.join(tabs)}")

    tabinfo = {}
    for t in tabs:
        cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (t,))
        cc = cur.fetchall()
        cols = [c for c, _ in cc]
        # 行数用 reltuples 估计（避免对超大表 count(*)）
        try:
            cur.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", ('public.' + t,))
            rr = cur.fetchone()
            est = int(rr[0]) if rr and rr[0] and rr[0] > 0 else None
        except Exception:
            conn.rollback(); est = None
        ids = [c for c in cols if PAT_ID.match(c)]
        tot = [c for c in cols if PAT_TOTAL.match(c)]
        art = [c for c in cols if PAT_ARTH.match(c)]
        comp = [c for c in cols if PAT_COMP.match(c)]
        tabinfo[t] = {'ncols': len(cols), 'est_rows': est, 'idcols': ids[:8],
                      'total': tot, 'arthre': art, 'components_n': len(comp),
                      'components': comp[:20], 'first_cols': cols[:8]}
        if tot or art:
            log(f"  {t}: cols={len(cols)} est_rows={est} ids={ids[:5]}")
            if tot:  log(f"     总额变量({len(tot)}): {', '.join(tot[:25])}")
            if art:  log(f"     arthre({len(art)}): {', '.join(art[:25])}")
            if comp: log(f"     分项({len(comp)}): {', '.join(comp[:20])}")
        elif len(cols) < 300:
            log(f"  {t}: cols={len(cols)} est_rows={est} ids={ids[:5]} sample={cols[:12]}")
    report[db] = tabinfo
    conn.close()

with open(os.path.join(OUT, '07_probe_structure.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '07_probe_structure.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 07_probe_structure.txt / .json")
