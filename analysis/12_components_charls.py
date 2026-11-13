# -*- coding: utf-8 -*-
"""方向 A 可行性（续）：① 支出分项缺失矩阵与分项加总对总额的一致性；
② CHARLS 自建年化总额（门诊×12 + 住院 + 牙科）与 EOL 表 harmonized 总额 raxoopmd1y_c 的公式对账。
只读；不做推断统计。结果落盘 12_components_charls.txt / .json。"""
import os, json, time, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '12_components_charls.txt')

COMP = {
 'mhas': dict(tab='h_mhas_d_p3', waves=[1,2,3,4,5,6], total=lambda w: f'r{w}oopmd1y',
   parts={f'doc1y': list(range(1,7)), 'hos1y': list(range(1,7)), 'den1y': list(range(1,7)),
          'osrg1y': list(range(1,7)), 'fhho1y': [1,2,3,4], 'drug1m': [3,4,5,6]},
   var=lambda w, p: f'r{w}oop{p}'),
 'share': dict(tab='gh_share_p4', waves=[1,2,5,6,7], total=lambda w: f'r{w}oopmd1y',
   parts={'doc1y':[1,2,5,6,7], 'drug1y':[1,2,5,6,7], 'hos1y':[1,2,5,6,7],
          'hcnh1y':[1,2,5,6,7], 'den1y':[5,6,7]},
   var=lambda w, p: f'r{w}oop{p}'),
 'lasi': dict(tab='gh_lasi_p1', waves=[1], total=lambda w: 'r1oopmd1y_l',
   parts={'doc1y':[1], 'hos1y':[1], 'supl1y':[1]},
   var=lambda w, p: f'r1oop{p}'),
 'charls': dict(tab='harm_h_charls_d_data_p2', waves=[1,2,3,4], total=None,
   parts={'doc1m':[1,2,3,4], 'hos1y':[1,2,3,4], 'den1y':[2,3]},
   var=lambda w, p: f'r{w}oop{p}'),
 'creles': dict(tab='h_creles', waves=[1,2,3,4,5], total=lambda w: f'r{w}oopmdv3m',
   parts={'hos1y':[1,2,3,4,5], 'spc1m':[1,2,3,4,5], 'oth1m':[1,2,3,4,5]},
   var=lambda w, p: f'r{w}oop{p}'),
}

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
def fmt(x, spec='.0f'):
    return format(x, spec) if x is not None else 'NA'

log("方向 A 可行性（续）：支出分项与 CHARLS 年化口径对账｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("说明：金额均为各库本币名义值；分项保持原始时间窗（doc1m/drug1m/spc1m 为月度，其余为年度）。\n")
report = {'components': {}, 'charls': {}}

for db, cfg in COMP.items():
    log(f"\n########## {db} 分项矩阵 [{cfg['tab']}] ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='240s'")
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s""", (cfg['tab'],))
    ocols = {x[0].lower() for x in cur.fetchall()}
    cur.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(cfg['tab'])))
    nrow = cur.fetchone()[0]
    log(f"  表行数 = {nrow:,}")
    report['components'][db] = {'table': cfg['tab'], 'nrow': nrow, 'waves': {}}

    for w in cfg['waves']:
        present = [(p, cfg['var'](w, p)) for p, ws in cfg['parts'].items() if w in ws
                   and cfg['var'](w, p).lower() in ocols]
        if not present:
            log(f"  w{w}: 无分项变量"); flush(); continue
        sel = sql.SQL(', ').join(
            sql.SQL('count({c}) AS {a}, count(*) FILTER (WHERE {c} = 0) AS {b}, '
                    'count(*) FILTER (WHERE {c} > 0) AS {d}, '
                    'percentile_cont(0.5) WITHIN GROUP (ORDER BY {c}) FILTER (WHERE {c} > 0) AS {e}'
                    ).format(c=c(v), a=sql.Identifier('n_'+p), b=sql.Identifier('z_'+p),
                             d=sql.Identifier('p_'+p), e=sql.Identifier('m_'+p))
            for p, v in present)
        q = sql.SQL('SELECT {sel} FROM public.{t}').format(sel=sel, t=sql.Identifier(cfg['tab']))
        try:
            cur.execute(q)
            r = cur.fetchone()
        except Exception as e:
            conn.rollback(); log(f"  w{w}: 失败 {str(e)[:140]}"); flush(); continue
        wd = {}
        for i, (p, v) in enumerate(present):
            n, z, pos, med = r[4*i:4*i+4]
            wd[p] = {'var': v, 'nonnull': n, 'zero': z, 'positive': pos,
                     'median_positive': float(med) if med is not None else None,
                     'coverage_pct': round(100*float(n)/nrow, 1)}
        report['components'][db]['waves'][w] = wd
        log(f"  w{w}: " + ' | '.join(
            f"{p}[{v}] 有值{wd[p]['coverage_pct']}% 正{wd[p]['positive']:,} 中位{fmt(wd[p]['median_positive'])}"
            for p, v in present))
        flush()

        # 分项加总 vs 总额一致性（CHARLS 无总额，跳过）
        if not cfg['total']:
            continue
        tv = cfg['total'](w)
        if tv.lower() not in ocols:
            continue
        # 月度项 ×12 后再加总
        exprs = []
        for p, v in present:
            mult = 12 if p.endswith('1m') else 1
            exprs.append(sql.SQL('COALESCE({}, 0) * {}').format(c(v), sql.Literal(mult)))
        s = sql.SQL(' + ').join(exprs)
        q2 = sql.SQL("""
          WITH j AS (
            SELECT {t} AS tot, {s} AS sm,
                   {nnonnull} AS ncomp
            FROM public.{tab}
          ), k AS (SELECT * FROM j WHERE tot IS NOT NULL AND tot >= 0 AND tot < 999996
                                        AND sm > 0 AND ncomp > 0)
          SELECT count(*),
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY sm / NULLIF(tot,0)) FILTER (WHERE tot > 0),
                 corr(tot, sm),
                 count(*) FILTER (WHERE abs(sm - tot) < 1),
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY sm),
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY tot)
          FROM k
        """).format(t=c(tv), s=s,
                    nnonnull=sql.SQL(' + ').join(
                        sql.SQL('(CASE WHEN {c} IS NOT NULL THEN 1 ELSE 0 END)').format(c=c(v))
                        for _, v in present),
                    tab=sql.Identifier(cfg['tab']))
        try:
            cur.execute(q2)
            n, ratio, cr, neq, ms, mt = cur.fetchone()
            consistency = {'n': n, 'median_sum_over_total': float(ratio) if ratio is not None else None,
                           'corr': float(cr) if cr is not None else None,
                           'n_exact_match': neq,
                           'median_sum': float(ms) if ms is not None else None,
                           'median_total': float(mt) if mt is not None else None}
            report['components'][db]['waves'][w]['_consistency'] = consistency
            log(f"     分项加总/总额: n={n:,} 中位比={fmt(consistency['median_sum_over_total'],'.3f')} "
                f"corr={fmt(consistency['corr'],'.3f')} 精确相等={neq:,} "
                f"| 分项和中位={fmt(consistency['median_sum'])} 总额中位={fmt(consistency['median_total'])}")
            flush()
        except Exception as e:
            conn.rollback(); log(f"     一致性检验失败 {str(e)[:120]}")
    conn.close()

# ---------------- CHARLS 自建年化总额 + EOL 对账 ----------------
log("\n########## CHARLS 自建年化总额 ##########")
conn = psycopg2.connect(CONN + " dbname=charls")
cur = conn.cursor()
cur.execute("SET statement_timeout='240s'")
cur.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name='harm_h_charls_eol_a'""")
eol = {x[0].lower() for x in cur.fetchall()}
log(f"  EOL 表含 oop 的列: {sorted(x for x in eol if 'oop' in x)}")
report['charls']['eol_oop_cols'] = sorted(x for x in eol if 'oop' in x)

# 在世波次：年化 = 月门诊×12 + 年住院 + 年牙科
for w in [1,2,3,4]:
    doc = f'r{w}oopdoc1m'; hos = f'r{w}oophos1y'; den = f'r{w}oopden1y'
    has_den = w in (2,3)
    parts = [sql.SQL('COALESCE({c},0)*12').format(c=c(doc)),
             sql.SQL('COALESCE({c},0)').format(c=c(hos))]
    nn = [sql.SQL('(CASE WHEN {c} IS NOT NULL THEN 1 ELSE 0 END)').format(c=c(doc)),
          sql.SQL('(CASE WHEN {c} IS NOT NULL THEN 1 ELSE 0 END)').format(c=c(hos))]
    if has_den:
        parts.append(sql.SQL('COALESCE({c},0)').format(c=c(den)))
        nn.append(sql.SQL('(CASE WHEN {c} IS NOT NULL THEN 1 ELSE 0 END)').format(c=c(den)))
    s = sql.SQL(' + ').join(parts); ncomp = sql.SQL(' + ').join(nn)
    q = sql.SQL("""
      WITH j AS (
        SELECT CASE WHEN {nc}=0 THEN NULL ELSE {s} END AS ann,
               {nc} AS ncomp,
               NULLIF({arth}::text,'')::numeric AS ar
        FROM public.harm_h_charls_d_data_p2
      ), v AS (SELECT * FROM j WHERE ann IS NOT NULL AND ann >= 0 AND ann < 999996)
      SELECT count(*), count(*) FILTER (WHERE ncomp = {nmax}),
             count(*) FILTER (WHERE ann = 0), avg(ann),
             percentile_cont(0.5) WITHIN GROUP (ORDER BY ann),
             percentile_cont(0.9) WITHIN GROUP (ORDER BY ann),
             percentile_cont(0.95) WITHIN GROUP (ORDER BY ann),
             percentile_cont(0.99) WITHIN GROUP (ORDER BY ann), max(ann),
             count(*) FILTER (WHERE ar=1), count(*) FILTER (WHERE ar=0),
             count(*) FILTER (WHERE ar=1 AND ann>0), count(*) FILTER (WHERE ar=0 AND ann>0),
             percentile_cont(0.5) WITHIN GROUP (ORDER BY ann) FILTER (WHERE ar=1 AND ann>0),
             percentile_cont(0.5) WITHIN GROUP (ORDER BY ann) FILTER (WHERE ar=0 AND ann>0)
      FROM v
    """).format(nc=ncomp, s=s, arth=sql.Identifier(f'r{w}arthre'),
                nmax=sql.Literal(3 if has_den else 2))
    try:
        cur.execute(q)
        r = cur.fetchone()
        names = ['n','n_complete','n_zero','mean','p50','p90','p95','p99','max',
                 'n_a1','n_a0','n_a1pos','n_a0pos','p50_a1pos','p50_a0pos']
        d = dict(zip(names, [float(x) if x is not None else None for x in r]))
        report['charls'][f'w{w}_derived'] = d
        log(f"  w{w} 自建年化总额: n={d['n']:,.0f} (三分量齐全 {d['n_complete']:,.0f}) "
            f"零值={fmt(100*d['n_zero']/d['n'],'.1f') if d['n'] else 'NA'}% "
            f"中位={fmt(d['p50'])} P90={fmt(d['p90'])} P95={fmt(d['p95'])} P99={fmt(d['p99'])} max={fmt(d['max'])} "
            f"| arthre+ ={d['n_a1']:,.0f} 对照={d['n_a0']:,.0f} "
            f"有支出率={fmt(100*d['n_a1pos']/d['n_a1'],'.1f') if d['n_a1'] else 'NA'}% vs "
            f"{fmt(100*d['n_a0pos']/d['n_a0'],'.1f') if d['n_a0'] else 'NA'}% "
            f"| 有支出者中位 {fmt(d['p50_a1pos'])} vs {fmt(d['p50_a0pos'])}")
    except Exception as e:
        conn.rollback(); log(f"  w{w} 自建失败 {str(e)[:160]}")
    flush()

# EOL 对账：验证 harmonized 总额的构成公式
log("\n  --- EOL 表 (harm_h_charls_eol_a, 408 行) 公式对账 ---")
need = ['raxoopmd1y_c','raxoopdoc1m','raxoophos1y','raxoopden1y','raxoopdrug1y','raxoopome1y_c']
have = [x for x in need if x in eol]
log(f"  可用列: {have}")
if 'raxoopmd1y_c' in eol:
    variants = {}
    # 候选公式
    def col(x): return sql.SQL('COALESCE({},0)').format(c(x))
    if 'raxoopdoc1m' in eol and 'raxoophos1y' in eol:
        variants['doc12+hos'] = sql.SQL('{d}*12 + {h}').format(d=col('raxoopdoc1m'), h=col('raxoophos1y'))
        if 'raxoopden1y' in eol:
            variants['doc12+hos+den'] = sql.SQL('{d}*12 + {h} + {n}').format(
                d=col('raxoopdoc1m'), h=col('raxoophos1y'), n=col('raxoopden1y'))
        if 'raxoopdrug1y' in eol:
            variants['doc12+hos+drug'] = sql.SQL('{d}*12 + {h} + {g}').format(
                d=col('raxoopdoc1m'), h=col('raxoophos1y'), g=col('raxoopdrug1y'))
            if 'raxoopden1y' in eol:
                variants['doc12+hos+den+drug'] = sql.SQL('{d}*12 + {h} + {n} + {g}').format(
                    d=col('raxoopdoc1m'), h=col('raxoophos1y'), n=col('raxoopden1y'), g=col('raxoopdrug1y'))
    for name, expr in variants.items():
        q = sql.SQL("""
          WITH j AS (SELECT NULLIF({tot}::text,'')::numeric AS t, {e} AS s
                     FROM public.harm_h_charls_eol_a),
          k AS (SELECT * FROM j WHERE t IS NOT NULL AND t>=0 AND t<999996)
          SELECT count(*), corr(t,s), count(*) FILTER (WHERE abs(t-s)<1),
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY s/NULLIF(t,0)) FILTER (WHERE t>0),
                 avg(t), avg(s) FROM k
        """).format(tot=c('raxoopmd1y_c'), e=expr)
        try:
            cur.execute(q)
            n, cr, neq, ratio, mt, ms = cur.fetchone()
            v = {'n': n, 'corr': float(cr) if cr is not None else None,
                 'n_exact': neq, 'median_ratio_s_over_t': float(ratio) if ratio is not None else None,
                 'mean_total': float(mt) if mt is not None else None,
                 'mean_formula': float(ms) if ms is not None else None}
            report['charls'][f'eol_formula_{name}'] = v
            log(f"    {name:<24}: n={n} corr={fmt(v['corr'],'.4f')} 精确相等={neq} "
                f"中位(公式/总额)={fmt(v['median_ratio_s_over_t'],'.3f')} "
                f"均值 总额={fmt(v['mean_total'])} 公式={fmt(v['mean_formula'])}")
        except Exception as e:
            conn.rollback(); log(f"    {name}: 失败 {str(e)[:120]}")
        flush()
conn.close()

with open(os.path.join(OUT, '12_components_charls.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 12_components_charls.txt / .json")
flush()
