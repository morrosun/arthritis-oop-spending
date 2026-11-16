# -*- coding: utf-8 -*-
"""核验主键、变量类型、取值编码、插补标记所在分片；并探测是否存在可直接用的长表。
只读。结果落盘 08_probe_keys_values.txt / .json。"""
import os, json, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))

CFG = {
    'mhas':  dict(key='rahhidnp', tabs=['h_mhas_d_p2', 'h_mhas_d_p3'],
                  probe_arth=['r1arthre', 'r6arthre'], probe_oop=['r1oopmd1y', 'r6oopmd1y'],
                  flags=['r1oopmdf1y', 'r6oopmdf1y']),
    'hrs':   dict(key='hhidpn', tabs=['randhrs1992_2022v1_p6', 'randhrs1992_2022v1_p7',
                                      'randhrs1992_2022v1_p2'],
                  probe_arth=['r2arthre', 'r16arthre'], probe_oop=['r2oopmd', 'r16oopmd'],
                  flags=['r2oopmdf', 'r16oopmdf', 'r10oopmdo']),
    'share': dict(key='mergeid', tabs=['gh_share_p3', 'gh_share_p4'],
                  probe_arth=['r1arthre', 'r7arthre'], probe_oop=['r1oopmd1y', 'r7oopmd1y'],
                  flags=['r1oopmdf1y', 'r7oopmdf1y']),
    'lasi':  dict(key='prim_key', tabs=['gh_lasi_p1'],
                  probe_arth=['r1arthre'], probe_oop=['r1oopmd1y_l'],
                  flags=['r1oopmdf1y_l']),
    'charls':dict(key='id', tabs=['harm_h_charls_d_data_p2', 'harm_h_charls_eol_a'],
                  probe_arth=['r1arthre', 'r4arthre'], probe_oop=['r1oopdoc1m', 'r1oophos1y'],
                  flags=['raxoopmd1y_c']),
}

lines = []
def log(s=''):
    print(s); lines.append(str(s))

report = {}
for db, cfg in CFG.items():
    log(f"\n########## {db} (key={cfg['key']}) ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='180s'")
    dbres = {'key': cfg['key'], 'tabs': {}, 'vars': {}, 'long_tables': [], 'labels': {}}

    # 所有 schema 里疑似长表
    cur.execute("""SELECT table_schema, table_name FROM information_schema.tables
                   WHERE table_type='BASE TABLE' AND (table_name ILIKE '%long%'
                     OR table_name ILIKE '%harm_long%') ORDER BY 1,2""")
    dbres['long_tables'] = [f"{a}.{b}" for a, b in cur.fetchall()]
    log(f"疑似长表: {dbres['long_tables'] or '无'}")

    for t in cfg['tabs']:
        cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s""", (t,))
        cmap = dict(cur.fetchall())
        has_key = cfg['key'] in cmap
        tinfo = {'ncols': len(cmap), 'has_key': has_key,
                 'key_type': cmap.get(cfg['key']), 'rows': None, 'key_distinct': None,
                 'key_null': None}
        if has_key:
            try:
                q = sql.SQL('SELECT count(*), count(DISTINCT {k}), count(*) FILTER (WHERE {k} IS NULL) FROM public.{t}').format(
                    k=sql.Identifier(cfg['key']), t=sql.Identifier(t))
                cur.execute(q)
                tinfo['rows'], tinfo['key_distinct'], tinfo['key_null'] = cur.fetchone()
            except Exception as e:
                conn.rollback(); tinfo['err'] = str(e)[:150]
        else:
            # 找候选 id 列
            tinfo['id_candidates'] = [c for c in cmap if c.lower() in
                ('id','pid','hhid','hhidpn','rahhidnp','mergeid','prim_key','idsujeto','idauniqc','__rn')][:12]
        dbres['tabs'][t] = tinfo
        log(f"  {t}: cols={tinfo['ncols']} key={cfg['key']} {'OK' if has_key else 'MISSING'} "
            f"rows={tinfo['rows']} distinct={tinfo['key_distinct']} keynull={tinfo['key_null']}"
            + (f" 候选ID={tinfo.get('id_candidates')}" if not has_key else ''))

    # 目标变量：所在表、类型、取值分布/金额范围
    allvars = cfg['probe_arth'] + cfg['probe_oop'] + cfg['flags']
    for v in allvars:
        cur.execute("""SELECT table_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND column_name=%s""", (v,))
        loc = cur.fetchall()
        if not loc:
            dbres['vars'][v] = {'found': False}
            log(f"    {v}: NOT FOUND")
            continue
        # 列名可能在多表出现，取第一个有该列的表
        tname, dtype = loc[0]
        vinfo = {'found': True, 'tables': [x[0] for x in loc], 'type': dtype, 'sample_table': tname}
        try:
            if v in cfg['probe_arth']:
                q = sql.SQL('SELECT {c}::text AS v, count(*) FROM public.{t} GROUP BY 1 ORDER BY 2 DESC LIMIT 15').format(
                    c=sql.Identifier(v), t=sql.Identifier(tname))
                cur.execute(q)
                vinfo['value_counts'] = {str(a): b for a, b in cur.fetchall()}
            else:
                q = sql.SQL("""SELECT count({c}) AS n_nonnull,
                                 count(*) FILTER (WHERE {c} = 0) AS n_zero,
                                 count(*) FILTER (WHERE {c} < 0) AS n_neg,
                                 count(*) FILTER (WHERE {c} >= 999996) AS n_sentinel,
                                 min({c})::float8, max({c})::float8
                               FROM public.{t}""").format(c=sql.Identifier(v), t=sql.Identifier(tname))
                cur.execute(q)
                r = cur.fetchone()
                vinfo['stats'] = dict(zip(['nonnull','zero','neg','sentinel','min','max'],
                                         [float(x) if x is not None else None for x in r]))
        except Exception as e:
            conn.rollback(); vinfo['err'] = str(e)[:180]
        dbres['vars'][v] = vinfo
        log(f"    {v}: [{dtype}] in {tname} -> {vinfo.get('value_counts') or vinfo.get('stats') or vinfo.get('err')}")

    # value_labels 表查 arthre 编码
    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema='public'
                   AND table_name ILIKE '%value_label%'""")
    for (lt,) in cur.fetchall():
        try:
            cur.execute("""SELECT column_name FROM information_schema.columns
                           WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (lt,))
            lc = [r[0] for r in cur.fetchall()]
            if len(lc) < 2: continue
            q = sql.SQL('SELECT * FROM public.{} WHERE {} ILIKE %s LIMIT 12').format(
                sql.Identifier(lt), sql.Identifier(lc[0]))
            cur.execute(q, ('%arthre%',))
            rows = cur.fetchall()
            if rows:
                dbres['labels'][lt] = [[str(x)[:100] for x in r] for r in rows]
                log(f"  标签 [{lt}]: {dbres['labels'][lt][:4]}")
        except Exception:
            conn.rollback()
    report[db] = dbres
    conn.close()

with open(os.path.join(OUT, '08_probe_keys_values.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '08_probe_keys_values.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 08_probe_keys_values.txt / .json")
