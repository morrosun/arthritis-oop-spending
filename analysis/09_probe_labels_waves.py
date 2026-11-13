# -*- coding: utf-8 -*-
"""查插补标记码本、OOPE 变量说明（含 HRS 时间窗）、波次年份映射、HRS text 列值域。
只读。结果落盘 09_probe_labels_waves.txt / .json。"""
import os, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['mhas', 'hrs', 'share', 'lasi', 'charls', 'creles']

lines = []
def log(s=''):
    print(s); lines.append(str(s))

report = {}
for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='120s'")
    r = {'flag_labels': {}, 'oop_labels': {}, 'wave_map': [], 'text_values': {}}

    # 所有标签表与其结构
    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema='public'
                   AND (table_name ILIKE '%label%' OR table_name ILIKE '%_vl') ORDER BY 1""")
    ltabs = [x[0] for x in cur.fetchall()]
    log(f"标签表: {ltabs}")

    for lt in ltabs:
        cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (lt,))
        cc = cur.fetchall()
        if len(cc) < 2: continue
        textcols = [c for c, d in cc if d in ('text','character varying','character')]
        if not textcols: continue
        namecol = next((c for c in textcols if 'var' in c.lower() or 'column' in c.lower() or c == 'name'), textcols[0])
        for key, kw in [('flag_labels', '%oopmd%f%'), ('oop_labels', '%oopmd%')]:
            try:
                q = sql.SQL('SELECT * FROM public.{} WHERE {} ILIKE %s LIMIT 40').format(
                    sql.Identifier(lt), sql.Identifier(namecol))
                cur.execute(q, (kw,))
                rows = cur.fetchall()
                if rows:
                    r[key][lt] = [[str(x)[:160] for x in row] for row in rows]
            except Exception:
                conn.rollback()
    for k in ('flag_labels', 'oop_labels'):
        for lt, rows in r[k].items():
            log(f"  [{k}] {lt} ({len(rows)} 条):")
            for row in rows[:14]:
                log(f"     {row}")

    # 波次年份映射
    for wt in [t for t in ltabs if False]:
        pass
    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema='public'
                   AND table_name ILIKE '%wave_map%'""")
    for (wt,) in cur.fetchall():
        try:
            cur.execute(sql.SQL('SELECT * FROM public.{} ORDER BY 1 LIMIT 20').format(sql.Identifier(wt)))
            rows = cur.fetchall()
            r['wave_map'] = [[str(x)[:60] for x in row] for row in rows]
            log(f"  [wave_map] {wt}: {r['wave_map']}")
        except Exception:
            conn.rollback()

    # HRS text 列值域（确认是否有 DK / 哨兵字符串）
    if db == 'hrs':
        for v, t in [('r2oopmd','randhrs1992_2022v1_p7'),
                     ('r16oopmd','randhrs1992_2022v1_p7'),
                     ('r2oopmdf','randhrs1992_2022v1_p7'),
                     ('r10oopmdo','randhrs1992_2022v1_p7'),
                     ('r2arthre','randhrs1992_2022v1_p6')]:
            cur.execute("""SELECT column_name FROM information_schema.columns
                           WHERE table_schema='public' AND table_name=%s AND column_name=%s""", (t, v))
            if not cur.fetchone(): continue
            try:
                q = sql.SQL('SELECT {c}::text, count(*) FROM public.{t} GROUP BY 1 ORDER BY 2 DESC LIMIT 12').format(
                    c=sql.Identifier(v), t=sql.Identifier(t))
                cur.execute(q)
                r['text_values'][v] = {str(a): b for a, b in cur.fetchall()}
                log(f"  [text值域] {v}: {r['text_values'][v]}")
                # 是否含非数字字符
                cur.execute(sql.SQL("""SELECT count(*) FROM public.{t}
                        WHERE {c} IS NOT NULL AND {c}::text !~ '^-?[0-9]+(\\.[0-9]+)?$'""").format(
                    c=sql.Identifier(v), t=sql.Identifier(t)))
                bad = cur.fetchone()[0]
                log(f"     非纯数字行数: {bad}")
            except Exception as e:
                conn.rollback(); log(f"  [text值域] {v} 失败 {str(e)[:120]}")
    report[db] = r
    conn.close()

with open(os.path.join(OUT, '09_probe_labels_waves.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '09_probe_labels_waves.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 09_probe_labels_waves.txt / .json")
