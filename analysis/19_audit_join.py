# -*- coding: utf-8 -*-
"""方向 A / 任务 10 审计：分片表主键唯一性 + 18 输出 CSV 的行级一致性。只读。
输出 19_audit_join.txt。"""
import os, glob, psycopg2, pandas as pd
from psycopg2 import sql
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
PREFIX = {'mhas':('h_mhas_d_p','rahhidnp'), 'hrs':('randhrs1992_2022v1_p','hhidpn'),
          'share':('gh_share_p','mergeid'), 'lasi':('gh_lasi_p','prim_key'),
          'charls':('harm_h_charls_d_data_p','id')}
lines = []
def log(s=''):
    print(s); lines.append(str(s))

log("方向 A / 任务 10 审计｜" + __import__('time').strftime('%Y-%m-%d %H:%M:%S'))
for db, (pref, key) in PREFIX.items():
    log(f"\n########## {db} ########## key={key}")
    conn = psycopg2.connect(CONN + " dbname=" + db); cur = conn.cursor()
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='public' AND table_name LIKE %s ORDER BY 1""",
                (pref.replace('_','\\_') + '%',))
    tabs = [r[0] for r in cur.fetchall()]
    for t in tabs:
        try:
            cur.execute(sql.SQL("""SELECT count(*) AS n, count(DISTINCT {k}) AS nd
                                   FROM public.{t}""").format(
                k=sql.Identifier(key), t=sql.Identifier(t)))
            n, nd = cur.fetchone()
            flag = ' <<< 重复!' if n != nd else ''
            log(f"  {t:<38s} rows={n:>8,} distinct({key})={nd:>8,}{flag}")
        except Exception as e:
            conn.rollback(); log(f"  {t}: 查询失败 {type(e).__name__} {str(e)[:90]}")
    conn.close()
    # CSV 行级检查
    p = os.path.join(OUT, f'18_data_{db}.csv')
    if os.path.exists(p):
        df = pd.read_csv(p, low_memory=False)
        dup = df.duplicated(subset=['wave','id']).sum()
        log(f"  CSV: {len(df):,} 行，(wave,id) 重复 = {dup:,}"
            f" | oop 缺失 = {df['oop_annual_lcu'].isna().sum():,}"
            f" | arth 均值 = {df['arth'].mean():.3f}")
        bad = df.groupby('wave').agg(n=('id','size'), oop_ok=('oop_annual_lcu','count'),
                                     che_ok=('che10_cons','count')).reset_index()
        log("  逐波: " + '; '.join(f"w{int(r.wave)} n={int(r.n):,} oop有值={int(r.oop_ok):,} 消费CHE={int(r.che_ok):,}"
                                  for r in bad.itertuples()))
with open(os.path.join(OUT, '19_audit_join.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
