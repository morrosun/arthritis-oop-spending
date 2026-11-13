# -*- coding: utf-8 -*-
"""方向 A / 任务 8：建模协变量的列->分片映射、取值编码与哨兵点查。
只读。附带判定 SHARE 金额是否已统一为跨国可比单位（按 country 分组看量级）。
输出 16_covariate_map.csv / .json、16_covariate_probe.txt，增量落盘。"""
import os, json, csv, time, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '16_covariate_probe.txt')

# 模板里 {w} 为波次；值为 list 时按次序取第一个实库存在的列
CFG = {
 'mhas': dict(key='rahhidnp', waves=[1, 3, 6], rep=3, prefix='h_mhas_d_p', cols=dict(
    oop='r{w}oopmd1y', flag='r{w}oopmdf1y', arth='r{w}arthre',
    age='r{w}agey', gender='ragender', educ='raeducl', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adla', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke', itot='h{w}itot',
    ctot='hh{w}ctot1m', rural='h{w}rural', weight='r{w}weight')),
 'hrs': dict(key='hhidpn', waves=[3, 10, 16], rep=10, prefix='randhrs1992_2022v1_p', cols=dict(
    oop='r{w}oopmd', flag='r{w}oopmdf', arth='r{w}arthre',
    age='r{w}agey_b', gender='ragender', educ='raeduc', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adl5a', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke', itot='h{w}itot',
    weight='r{w}weight')),
 'share': dict(key='mergeid', waves=[1, 2, 5, 6], rep=6, prefix='gh_share_p', cols=dict(
    oop='r{w}oopmd1y', flag='r{w}oopmdf1y', arth='r{w}arthre',
    age='r{w}agey', gender='ragender', educ='raeducl', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adla', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke',
    itot=['hh{w}itothhinc', 'hh{w}itot', 'hh1itot'],
    ctot='hh1ctot1m', rural='h{w}rural', weight='r{w}weight', country='country')),
 'lasi': dict(key='prim_key', waves=[1], rep=1, prefix='gh_lasi_p', cols=dict(
    oop='r1oopmd1y_l', flag='r1oopmdf1y_l', arth='r1arthre',
    age='r1agey', gender='ragender', educ='raeduc_l', mstat='r1mstat',
    shlt='r1shlt', adl='r1adla', diabe='r1diabe', hibpe='r1hibpe',
    hearte='r1hearte', stroke='r1stroke', itot='hh1itot', ctot='hh1ctot',
    rural='h1rural', weight='indiaindividualweight')),
 'charls': dict(key='id', waves=[1, 3, 4], rep=3, prefix='harm_h_charls_d_data_p', cols=dict(
    oopdoc='r{w}oopdoc1m', oophos='r{w}oophos1y', arth='r{w}arthre',
    age='r{w}agey', gender='ragender', educ='raeduc_c', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adla_c', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke', itot='hh{w}itot', ctot='hh{w}ctot',
    rural='r{w}rural2', weight='r{w}mweight')),
}
DISCRETE = {'gender','educ','mstat','shlt','adl','diabe','hibpe','hearte','stroke',
            'rural','country','flag','arth'}
META = ('catalog','keys','value_label','variable_label','wave_map','_vl','_hcap_',
        'covid','_eol','_lh_','gvwt','harm_map','_long','_biom','_bm_','_psu','_weight')

lines = []
def log(s=''):
    print(s); lines.append(str(s))
def flush():
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def c(col, alias=None):
    ident = sql.Identifier(col)
    if alias:
        ident = sql.SQL("{}.{}").format(sql.Identifier(alias), ident)
    return sql.SQL("NULLIF({}::text, '')::numeric").format(ident)

log("方向 A / 任务 8：建模协变量编码与哨兵点查｜生成 " + time.strftime('%Y-%m-%d %H:%M:%S'))
log("只读；所有列一律 NULLIF(col::text,'')::numeric 后统计（HRS 全库 financial 为 text）。")
log("注意：本脚本不做任何模型拟合。\n")

maprows = []
for db, cfg in CFG.items():
    log(f"\n########## {db} ##########  key={cfg['key']}")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='240s'")
    cur.execute("""SELECT table_name, column_name, data_type FROM information_schema.columns
                   WHERE table_schema='public' ORDER BY table_name, ordinal_position""")
    colmap = {}
    for t, col, dt in cur.fetchall():
        if any(m in t.lower() for m in META):
            continue
        colmap.setdefault(col.lower(), []).append((t, dt))
    # 优先主 data 分片
    def pick(col):
        cand = colmap.get(col.lower())
        if not cand:
            return None, None
        pref = [x for x in cand if cfg['prefix'] in x[0]]
        return (pref or cand)[0]
    # 解析每波次的列名与所在表
    resolved = {}
    for w in cfg['waves']:
        for concept, tpl in cfg['cols'].items():
            tpls = tpl if isinstance(tpl, list) else [tpl]
            hit = None
            for t in tpls:
                name = t.format(w=w)
                tb, dt = pick(name)
                if tb:
                    hit = (name, tb, dt); break
            if hit:
                resolved[(w, concept)] = hit
                maprows.append(dict(db=db, wave=w, concept=concept, column=hit[0],
                                    table=hit[1], dtype=hit[2]))
            else:
                log(f"  w{w} [{concept}] 未找到列 (候选 {[t.format(w=w) for t in tpls]})")
        flush()
    # 每波次完整性
    for w in cfg['waves']:
        got = [k[1] for k in resolved if k[0] == w]
        miss = [c for c in cfg['cols'] if c not in got]
        log(f"  w{w}: 命中 {len(got)}/{len(cfg['cols'])} 个概念；缺 = {miss}")
    flush()

    # ---- 代表波：按表分组做聚合（范围/负值/零值/哨兵） ----
    w = cfg['rep']
    by_table = {}
    for (ww, concept), (col, tb, dt) in resolved.items():
        if ww == w:
            by_table.setdefault(tb, []).append((concept, col))
    log(f"  --- 代表波 w{w} 分布点查（{len(by_table)} 张分片）---")
    for tb, pairs in by_table.items():
        parts = []
        names = []
        for concept, col in pairs:
            cc = c(col)
            parts.append(sql.SQL("""count({cc}) AS {n1}, min({cc}) AS {n2}, max({cc}) AS {n3},
                 count(*) FILTER (WHERE {cc} < 0) AS {n4},
                 count(*) FILTER (WHERE {cc} = 0) AS {n5},
                 count(*) FILTER (WHERE {cc} >= 999996) AS {n6}""").format(
                cc=cc, n1=sql.Identifier(concept+'_n'), n2=sql.Identifier(concept+'_min'),
                n3=sql.Identifier(concept+'_max'), n4=sql.Identifier(concept+'_neg'),
                n5=sql.Identifier(concept+'_zero'), n6=sql.Identifier(concept+'_sent')))
            names.append(concept)
        q = sql.SQL("SELECT {p} FROM public.{t}").format(
            p=sql.SQL(', ').join(parts), t=sql.Identifier(tb))
        try:
            cur.execute(q); r = cur.fetchone()
        except Exception as e:
            conn.rollback(); log(f"    [{tb}] 聚合失败 {type(e).__name__} {str(e)[:120]}"); flush(); continue
        vals = [float(x) if x is not None else None for x in r]
        for i, concept in enumerate(names):
            n, mn, mx, neg, zero, sent = vals[i*6:(i+1)*6]
            log(f"    {concept:<9s} [{tb}] n={n:,.0f} min={mn} max={mx} neg={neg:,.0f} zero={zero:,.0f} >=999996={sent:,.0f}")
        flush()
        # 离散列频数（原值，numeric 归一化后）
        for concept, col in pairs:
            if concept not in DISCRETE:
                continue
            if concept == 'country':
                fq = sql.SQL("SELECT {x}::text, count(*) FROM public.{t} GROUP BY 1 ORDER BY 2 DESC LIMIT 15").format(
                    x=sql.Identifier(col), t=sql.Identifier(tb))
            else:
                fq = sql.SQL("SELECT {x}::text, count(*) FROM public.{t} GROUP BY 1 ORDER BY 2 DESC LIMIT 15").format(
                    x=c(col), t=sql.Identifier(tb))
            try:
                cur.execute(fq)
                fd = [(str(a), int(b)) for a, b in cur.fetchall()]
                log(f"      freq[{concept}] {fd}")
            except Exception as e:
                conn.rollback(); log(f"      freq[{concept}] 失败 {str(e)[:90]}")
            flush()

    # ---- SHARE 单位判定：按国家看 oop / income 量级 ----
    if db == 'share':
        log("\n  --- SHARE 金额单位判定：按 country 分组看 w6 中位 ---")
        try:
            oop_t = pick('r6oopmd1y')[0]
            inc_t = pick('hh6itothhinc')[0]
            cty_t = pick('country')[0]
            log(f"      oop 表={oop_t} / income 表={inc_t} / country 表={cty_t}")
            q = sql.SQL("""SELECT k.{cty}::text AS country, count(*) AS n,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY o.{op}) AS p50_oop,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY i.{ic}) AS p50_inc
                  FROM public.{t} k
                  JOIN public.{ot} o USING (mergeid)
                  JOIN public.{it} i USING (mergeid)
                  WHERE o.{op} IS NOT NULL AND o.{op} >= 0 AND o.{op} < 999996
                    AND i.{ic} IS NOT NULL AND i.{ic} > 0
                  GROUP BY 1 ORDER BY 2 DESC LIMIT 30""").format(
                cty=sql.Identifier('country'), op=sql.Identifier('r6oopmd1y'),
                ic=sql.Identifier('hh6itothhinc'), t=sql.Identifier(cty_t),
                ot=sql.Identifier(oop_t), it=sql.Identifier(inc_t))
            cur.execute(q)
            for country, n, p50o, p50i in cur.fetchall():
                log(f"      {str(country):<8s} n={n:>7,}  oop中位={(p50o or 0):>12,.0f}  income中位={(p50i or 0):>14,.0f}")
        except Exception as e:
            conn.rollback(); log(f"      SHARE 单位判定失败 {type(e).__name__} {str(e)[:180]}")
        # 找变量标签表结构
        cur.execute("""SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position)
                       FROM information_schema.columns WHERE table_schema='public'
                         AND (table_name LIKE '%label%' OR table_name LIKE '%_vl%' OR table_name LIKE '%catalog%')
                       GROUP BY 1 ORDER BY 1""")
        log("      标签类表结构: " + str(cur.fetchall()))
        flush()
    conn.close()

with open(os.path.join(OUT, '16_covariate_map.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=['db','wave','concept','column','table','dtype'])
    wr.writeheader(); wr.writerows(maprows)
with open(os.path.join(OUT, '16_covariate_map.json'), 'w', encoding='utf-8') as f:
    json.dump(maprows, f, ensure_ascii=False, indent=1)
log(f"\nDONE: 映射 {len(maprows)} 条 -> 16_covariate_map.csv / .json")
flush()
