# -*- coding: utf-8 -*-
"""方向 A 可行性描述表（主）：逐库逐波 OOPE 分布 + 关节炎交叉样本量 + 插补标记分布。
只读；金额一律换算为「年化、本币名义值」：HRS w3-16 除以 2，CRELES 3 个月乘 4。
结果增量落盘 11_feasibility_main.txt，最终汇总 11_feasibility_main.json / .csv。
注意：本脚本只做描述统计，不做任何推断统计与模型拟合。"""
import os, json, csv, time, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '11_feasibility_main.txt')

CFG = {
 'mhas': dict(key='rahhidnp', oop_tab='h_mhas_d_p3', arth_tab='h_mhas_d_p2',
              waves=[1,2,3,4,5,6], oop=lambda w: f'r{w}oopmd1y',
              flag=lambda w: f'r{w}oopmdf1y', arth=lambda w: f'r{w}arthre',
              div=lambda w: 1.0, imputed='f = 1', years={1:2001,2:2003,3:2012,4:2015,5:2018,6:2021},
              note='12 个月口径；flag 0=未插补 / 1=已插补'),
 'hrs': dict(key='hhidpn', oop_tab='randhrs1992_2022v1_p7', arth_tab='randhrs1992_2022v1_p6',
              waves=list(range(2,17)), oop=lambda w: f'r{w}oopmd',
              flag=lambda w: f'r{w}oopmdf', arth=lambda w: f'r{w}arthre',
              div=lambda w: 1.0 if w==2 else 2.0, imputed='f > 0',
              years={w: 1992+2*(w-1) for w in range(2,17)},
              note='w2=12 个月，w3–w16=2 年；text 列需 cast；flag 0=未插补，>0 见分布'),
 'share': dict(key='mergeid', oop_tab='gh_share_p4', arth_tab='gh_share_p3',
              waves=[1,2,5,6,7], oop=lambda w: f'r{w}oopmd1y',
              flag=lambda w: f'r{w}oopmdf1y', arth=lambda w: f'r{w}arthre',
              div=lambda w: 1.0, imputed='f IN (2,3,5,7)',
              years={1:2004,2:2007,5:2013,6:2015,7:2017},
              note='12 个月；flag 0/1=原始连续值，2/3=区间插补，5/7=缺失或 DK，6=无支出，-4=w7 简版问卷'),
 'lasi': dict(key='prim_key', oop_tab='gh_lasi_p1', arth_tab='gh_lasi_p1',
              waves=[1], oop=lambda w: 'r1oopmd1y_l',
              flag=lambda w: 'r1oopmdf1y_l', arth=lambda w: 'r1arthre',
              div=lambda w: 1.0, imputed='f IN (2,3,5,7)',
              years={1:2017},
              note='12 个月；单波横断面；flag 编码同 SHARE 体系'),
 'creles': dict(key='idsujeto', oop_tab='h_creles', arth_tab='h_creles',
              waves=[1,2,3,4,5], oop=lambda w: f'r{w}oopmdv3m',
              flag=None, arth=lambda w: f'r{w}arthre',
              div=lambda w: 0.25, imputed=None,
              years={1:2005,2:2007,3:2009,4:2012,5:2015},
              note='3 个月口径，×4 年化；无插补标记；双队列不重叠，仅作敏感性'),
}

lines = []
def log(s=''):
    print(s); lines.append(str(s))
def flush():
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def fmt(x, spec='.0f'):
    return format(x, spec) if x is not None else 'NA'

def c(col, alias=None):
    """统一把任意类型列安全转 numeric（HRS 是 text，其余 double precision）。"""
    ident = sql.Identifier(col)
    if alias:
        ident = sql.SQL("{}.{}").format(sql.Identifier(alias), ident)
    return sql.SQL("NULLIF({}::text, '')::numeric").format(ident)

log("方向 A 可行性描述表（主表）｜生成时间 " + time.strftime('%Y-%m-%d %H:%M:%S'))
log("口径：金额为各库本币名义值，已统一换算为「12 个月（年化）」；剔除 >=999996 的哨兵与负值；")
log("暴露 arthre 为自报 ever-diagnosed 关节炎/风湿（0/1），仅取受访者本人 r 系列；")
log("下列组间差异均为描述性，未作任何校正或推断。\n")

rows = []
flagdist = {}
for db, cfg in CFG.items():
    log(f"\n########## {db} ##########  {cfg['note']}")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='240s'")
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s""", (cfg['oop_tab'],))
    ocols = {r[0].lower() for r in cur.fetchall()}
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s""", (cfg['arth_tab'],))
    acols = {r[0].lower() for r in cur.fetchall()}

    for w in cfg['waves']:
        ov, av = cfg['oop'](w), cfg['arth'](w)
        fv = cfg['flag'](w) if cfg['flag'] else None
        if ov.lower() not in ocols or av.lower() not in acols:
            log(f"  w{w}: 缺列 oop={ov in ocols} arth={av in acols} -> SKIP"); flush(); continue
        flag_ok = bool(fv and fv.lower() in ocols)
        fexpr = c(fv) if flag_ok else sql.SQL('NULL::numeric')
        imp_expr = sql.SQL(cfg['imputed']) if (cfg['imputed'] and flag_ok) else sql.SQL('FALSE')
        div = cfg['div'](w)
        key = cfg['key']
        same = cfg['oop_tab'] == cfg['arth_tab']
        if same:
            src = sql.SQL("""SELECT {v} / %s AS v, {f} AS f, {a} AS ar FROM public.{t}""").format(
                v=c(ov), f=fexpr, a=c(av), t=sql.Identifier(cfg['oop_tab']))
        else:
            src = sql.SQL("""SELECT {v} / %s AS v, {f} AS f, {a} AS ar
                             FROM public.{ot} o JOIN public.{at} a USING ({k})""").format(
                v=c(ov, 'o'), f=(c(fv, 'o') if flag_ok else sql.SQL('NULL::numeric')),
                a=c(av, 'a'), ot=sql.Identifier(cfg['oop_tab']),
                at=sql.Identifier(cfg['arth_tab']), k=sql.Identifier(key))
        q = sql.SQL("""
          WITH src AS ({src}),
          valid AS (SELECT * FROM src WHERE v IS NOT NULL AND v >= 0 AND v < 999996)
          SELECT
            (SELECT count(*) FROM src) AS n_join,
            count(*) AS n_valid,
            count(v) FILTER (WHERE v = 0) AS n_zero,
            avg(v) AS mean,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY v) AS p50,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY v) AS p75,
            percentile_cont(0.90) WITHIN GROUP (ORDER BY v) AS p90,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY v) AS p95,
            percentile_cont(0.99) WITHIN GROUP (ORDER BY v) AS p99,
            max(v) AS mx,
            count(*) FILTER (WHERE ar = 1) AS n_arth1,
            count(*) FILTER (WHERE ar = 0) AS n_arth0,
            count(*) FILTER (WHERE ar IS NULL) AS n_arthNA,
            count(*) FILTER (WHERE ar = 1 AND v > 0) AS n_arth1_pos,
            count(*) FILTER (WHERE ar = 0 AND v > 0) AS n_arth0_pos,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY v) FILTER (WHERE ar = 1 AND v > 0) AS p50_a1pos,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY v) FILTER (WHERE ar = 0 AND v > 0) AS p50_a0pos,
            avg(v) FILTER (WHERE ar = 1) AS mean_a1,
            avg(v) FILTER (WHERE ar = 0) AS mean_a0,
            count(*) FILTER (WHERE {imp}) AS n_imputed,
            count(*) FILTER (WHERE f IS NOT NULL AND f > 0) AS n_flagpos
          FROM valid
        """).format(src=src, imp=imp_expr)
        t0 = time.time()
        try:
            cur.execute(q, (div,))
            r = cur.fetchone()
        except Exception as e:
            conn.rollback()
            log(f"  w{w}: 查询失败 {type(e).__name__} {str(e)[:160]}"); flush(); continue
        names = ['n_join','n_valid','n_zero','mean','p50','p75','p90','p95','p99','max',
                 'n_arth1','n_arth0','n_arthNA','n_arth1_pos','n_arth0_pos','p50_a1pos','p50_a0pos',
                 'mean_a1','mean_a0','n_imputed','n_flagpos']
        d = dict(zip(names, [float(x) if x is not None else None for x in r]))
        if not flag_ok:
            d['n_imputed'] = None
            d['n_flagpos'] = None
        d.update(db=db, wave=w, year=cfg['years'].get(w), divisor=div,
                 oop_var=ov, arth_var=av, flag_var=fv, flag_ok=flag_ok,
                 secs=round(time.time()-t0, 1))
        n = d['n_valid'] or 0
        d['zero_pct'] = round(100*d['n_zero']/n, 1) if n else None
        d['imputed_pct'] = (round(100*d['n_imputed']/n, 1)
                            if (n and d['n_imputed'] is not None) else None)
        d['arth_prevalence_pct'] = (round(100*d['n_arth1']/(d['n_arth1']+d['n_arth0']), 1)
                                    if (d['n_arth1']+d['n_arth0']) else None)
        d['posrate_a1_pct'] = round(100*d['n_arth1_pos']/d['n_arth1'], 1) if d['n_arth1'] else None
        d['posrate_a0_pct'] = round(100*d['n_arth0_pos']/d['n_arth0'], 1) if d['n_arth0'] else None
        d['median_ratio_a1_a0'] = (round(d['p50_a1pos']/d['p50_a0pos'], 3)
                                   if d['p50_a1pos'] and d['p50_a0pos'] else None)
        rows.append(d)
        log(f"  w{w} ({d['year']}) div={div}: N有效={n:,.0f} 零值={fmt(d['zero_pct'],'.1f')}% "
            f"中位={fmt(d['p50'])} P90={fmt(d['p90'])} P95={fmt(d['p95'])} P99={fmt(d['p99'])} max={fmt(d['max'])} "
            f"插补={fmt(d['imputed_pct'],'.1f')}% | arthre+ ={d['n_arth1']:,.0f} 对照={d['n_arth0']:,.0f} "
            f"患病率(有效样本内)={fmt(d['arth_prevalence_pct'],'.1f')}% | 有支出率 {fmt(d['posrate_a1_pct'],'.1f')}% vs {fmt(d['posrate_a0_pct'],'.1f')}% "
            f"| 有支出者中位 {fmt(d['p50_a1pos'])} vs {fmt(d['p50_a0pos'])} (比={fmt(d['median_ratio_a1_a0'],'.3f')}) "
            f"[{d['secs']}s]")
        flush()

        # flag 完整分布（每库只做第一个波 + 有异常的波）
        if fv and fv.lower() in ocols and (w == cfg['waves'][0] or w in (7, 16)):
            try:
                fq = sql.SQL("SELECT {f} AS f, count(*) FROM public.{t} GROUP BY 1 ORDER BY 2 DESC LIMIT 14").format(
                    f=c(fv), t=sql.Identifier(cfg['oop_tab']))
                cur.execute(fq)
                fd = {str(a): int(b) for a, b in cur.fetchall()}
                flagdist[f'{db}_w{w}_{fv}'] = fd
                log(f"      flag 分布 [{fv}]: {fd}")
                flush()
            except Exception as e:
                conn.rollback(); log(f"      flag 分布失败 {str(e)[:100]}")
    conn.close()

# CSV / JSON
with open(os.path.join(OUT, '11_feasibility_main.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    wr.writeheader(); wr.writerows(rows)
with open(os.path.join(OUT, '11_feasibility_main.json'), 'w', encoding='utf-8') as f:
    json.dump({'rows': rows, 'flag_distributions': flagdist}, f, ensure_ascii=False, indent=1)
log(f"\nDONE: {len(rows)} 个 (库, 波) 组合 -> 11_feasibility_main.txt / .csv / .json")
flush()
