# -*- coding: utf-8 -*-
"""AGING_DB 实库变量点查：风湿/自付医疗支出/结局 三类变量在各库的可得性。
只读，不修改任何数据库。结果落盘到 out/01_var_scan.txt 与 .json。"""
import os, re, json, collections, psycopg2

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['charls', 'clhls', 'hrs', 'share', 'lasi', 'klosa', 'mhas', 'creles', 'elsa', 'elsa_raw']

GROUPS = {
    'RHEUM': ['arth', 'rheum', 'osteo', 'gout', 'uric', 'lupus', 'autoimm',
              'psoria', 'fibromy', 'joint', 'fractur', 'backpain', 'pain', 'nsaid', 'steroid'],
    'OOP': ['oop', 'outofpocket', 'expend', 'medexp', 'cost', 'spend', 'drug',
            'hosp', 'doctor', 'insur', 'medic', 'pay', 'fee', 'income', 'wealth', 'itot'],
    'OUTCOME': ['frail', 'dth', 'mort', 'cesd', 'depress', 'adl', 'cog', 'srh', 'shlt', 'grip', 'walk'],
}

# 精确关注：OOPE 官方 harmonized 变量词干
OOP_STEMS = ['oopmd', 'oophos', 'oopdoc', 'oopden', 'ooposrg', 'oopfhho', 'oopdrug', 'oopmdf',
             'medexp', 'oop', 'hsexp', 'mdexp', 'doctorexp', 'drugexp']

lines = []
def log(s=''):
    print(s)
    lines.append(str(s))

result = {}
label_hits = {}

for db in DBS:
    try:
        conn = psycopg2.connect(CONN + " dbname=" + db)
        cur = conn.cursor()
        cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                       WHERE table_schema='public' ORDER BY table_name, ordinal_position""")
        rows = cur.fetchall()
        cols = [c for _, c in rows]
        uniq = list(dict.fromkeys(cols))
        log(f"\n=== {db}: {len(rows)} 列(含分片重复) / {len(uniq)} 个不同列名 ===")

        dbres = {'n_columns': len(rows), 'n_unique': len(uniq), 'groups': {}, 'oop_exact': {}}
        for g, kws in GROUPS.items():
            gres = {}
            for kw in kws:
                hit = [c for c in uniq if kw in c.lower()]
                gres[kw] = hit
            dbres['groups'][g] = gres
            cnt = sum(len(v) for v in gres.values())
            log(f"  [{g}] 关键词命中合计 {cnt} 个不同列名")
            for kw in kws:
                h = gres[kw]
                if h:
                    log(f"    {kw:<12} n={len(h):<5} e.g. {', '.join(h[:12])}")

        # OOPE 精确词干
        for stem in OOP_STEMS:
            hit = [c for c in uniq if stem in c.lower()]
            if hit:
                dbres['oop_exact'][stem] = hit
        log("  [OOPE 精确词干] " + (", ".join(f"{k}:{len(v)}" for k, v in dbres['oop_exact'].items()) or "无"))
        for k, v in dbres['oop_exact'].items():
            if k in ('oopmd', 'oophos', 'oopdoc', 'oopden', 'ooposrg', 'oopdrug', 'oop', 'medexp'):
                log(f"    {k}: {', '.join(v[:25])}")

        # 标签表语义反查
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema='public' AND (table_name ILIKE '%label%' OR table_name ILIKE '%_vl')""")
        ltabs = [r[0] for r in cur.fetchall()]
        lhits = collections.defaultdict(list)
        for t in ltabs:
            cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                           WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (t,))
            tcols = cur.fetchall()
            textcols = [c for c, d in tcols if d in ('text', 'character varying', 'character')]
            varcols = [c for c in textcols if 'var' in c.lower() or 'column' in c.lower() or 'name' in c.lower()]
            if not textcols or not varcols:
                continue
            vcol = varcols[0]
            conds = " OR ".join(["%s ILIKE %%s"] * len(textcols))
            params = [t]
            for _ in textcols:
                params.append('%arthrit%')
            try:
                q = f'SELECT * FROM public."{t}" WHERE ' + " OR ".join([f'"{c}" ILIKE %s' for c in textcols])
                cur.execute(q, tuple(['%arthrit%'] * len(textcols)))
                for r in cur.fetchall()[:40]:
                    lhits['arthritis'].append((t, [str(x)[:120] for x in r]))
                cur.execute(q, tuple(['%rheumat%'] * len(textcols)))
                for r in cur.fetchall()[:40]:
                    lhits['rheumatism'].append((t, [str(x)[:120] for x in r]))
                cur.execute(q, tuple(['%out-of-pocket%'] * len(textcols)))
                for r in cur.fetchall()[:40]:
                    lhits['out-of-pocket'].append((t, [str(x)[:120] for x in r]))
                cur.execute(q, tuple(['%gout%'] * len(textcols)))
                for r in cur.fetchall()[:40]:
                    lhits['gout'].append((t, [str(x)[:120] for x in r]))
            except Exception as e:
                conn.rollback()
                lhits['_err'].append((t, [str(e)[:150]]))
        label_hits[db] = {k: v[:40] for k, v in lhits.items()}
        log(f"  [标签表] {ltabs[:8]}；语义命中: " +
            ", ".join(f"{k}={len(v)}" for k, v in lhits.items() if k != '_err'))
        for k in ('arthritis', 'rheumatism', 'out-of-pocket', 'gout'):
            for t, vals in lhits.get(k, [])[:8]:
                log(f"    {k:<15} {t}: {vals}")

        result[db] = dbres
        conn.close()
    except Exception as e:
        log(f"=== {db}: 连接/查询失败 {type(e).__name__}: {e}")

with open(os.path.join(OUT, '01_var_scan.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '01_var_scan.json'), 'w', encoding='utf-8') as f:
    json.dump({'columns': result, 'labels': label_hits}, f, ensure_ascii=False, indent=1)
log("\nDONE -> 01_var_scan.txt / 01_var_scan.json")
