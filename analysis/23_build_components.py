# -*- coding: utf-8 -*-
"""方向 A / A2 数据层：构建支出分项数据集（只读抽取）。
把各库 harmonized 支出分项抽成人-波级宽表，与 18_data_<db>.csv 的
总额/暴露/协变量/平减因子对齐，并验证「分项加总 == 年化总额」的会计恒等式。

统一大类：drug / outpatient / inpatient / dental / other，另留 folk 单列（MHAS 民间治疗师）。
月度项（*1m）年化 ×12；未问的大类按 0（因 harmonized 总额本身亦不含该项），另以 avail_* 标记。
输出：23_data_components.csv、23_component_check.txt、23_component_check.csv
"""
import os, time, warnings, psycopg2, pandas as pd, numpy as np
from psycopg2 import sql
warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '23_component_check.txt')

CFG = {
 'mhas': dict(key='rahhidnp', tab='h_mhas_d_p3', waves=list(range(1,7)),
   parts={'outpatient':('r{w}oopdoc1y',1,list(range(1,7))),
          'inpatient':('r{w}oophos1y',1,list(range(1,7))),
          'dental':('r{w}oopden1y',1,list(range(1,7))),
          'other':('r{w}ooposrg1y',1,list(range(1,7))),
          'folk':('r{w}oopfhho1y',1,[1,2,3,4]),
          'drug':('r{w}oopdrug1m',12,[3,4,5,6])}),
 'share': dict(key='mergeid', tab='gh_share_p4', waves=[1,2,5,6],
   parts={'outpatient':('r{w}oopdoc1y',1,[1,2,5,6]),
          'inpatient':('r{w}oophos1y',1,[1,2,5,6]),
          'drug':('r{w}oopdrug1y',1,[1,2,5,6]),
          'other':('r{w}oophcnh1y',1,[1,2,5,6]),
          'dental':('r{w}oopden1y',1,[5,6])}),
 'lasi': dict(key='prim_key', tab='gh_lasi_p1', waves=[1],
   parts={'outpatient':('r1oopdoc1y',1,[1]),
          'inpatient':('r1oophos1y',1,[1]),
          'other':('r1oopsupl1y',1,[1])}),
 'charls': dict(key='id', tab='harm_h_charls_d_data_p2', waves=[1,2,3,4],
   parts={'outpatient':('r{w}oopdoc1m',12,[1,2,3,4]),
          'inpatient':('r{w}oophos1y',1,[1,2,3,4]),
          'dental':('r{w}oopden1y',1,[2,3])}),
}
CATS = ['drug','outpatient','inpatient','dental','other']
lines = []
def log(s=''):
    print(s, flush=True); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
def c(col):
    return sql.SQL("NULLIF({}::text, '')::numeric").format(sql.Identifier(col))
def norm_id(s):
    s = s.astype(str).str.strip()
    return s.str.replace(r'\.0$', '', regex=True).str.replace(r'\.000000$', '', regex=True)

log("方向 A / A2 数据层：支出分项抽取与会计恒等式核验｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("只读数据库；HRS 无任何支出分项，不进 A2。月度项 ×12 年化。\n")

checks, frames = [], []
for db, cfg in CFG.items():
    log(f"########## {db} ########## 表={cfg['tab']} 波={cfg['waves']}")
    base = pd.read_csv(os.path.join(OUT, f'18_data_{db}.csv'), low_memory=False, dtype={'id':str})
    base['id'] = norm_id(base['id'])
    conn = psycopg2.connect(CONN + ' dbname=' + db); cur = conn.cursor()
    cur.execute("SET statement_timeout='300s'")
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s""", (cfg['tab'],))
    ocols = {x[0].lower() for x in cur.fetchall()}
    for w in cfg['waves']:
        t0 = time.time()
        present = []
        for cat, (tpl, mult, ws) in cfg['parts'].items():
            if w not in ws: continue
            name = tpl.format(w=w)
            if name.lower() in ocols: present.append((cat, name, mult))
        if not present:
            log(f"  w{w}: 无分项"); continue
        sel = [sql.SQL("{}.{} AS id").format(sql.Identifier('a'), sql.Identifier(cfg['key']))]
        for cat, name, mult in present:
            sel.append(sql.SQL("{c} AS {a}").format(c=c(name), a=sql.Identifier('v_'+cat)))
        q = sql.SQL("SELECT {s} FROM public.{t} a").format(s=sql.SQL(', ').join(sel),
                                                            t=sql.Identifier(cfg['tab']))
        try:
            cur.execute(q); raw = pd.DataFrame(cur.fetchall(),
                        columns=[d[0] for d in cur.description])
        except Exception as e:
            conn.rollback(); log(f"  w{w}: SQL 失败 {type(e).__name__} {str(e)[:160]}"); continue
        raw['id'] = norm_id(raw['id'])
        # 同一波内主键去重（审计已确认唯一，此处防御）
        raw = raw.drop_duplicates('id', keep='first')
        for cat, name, mult in present:
            v = pd.to_numeric(raw['v_'+cat], errors='coerce')
            v = v.where((v >= 0) & (v < 999996))     # 哨兵 -> 缺失
            raw['c_'+cat] = v * mult                  # 年化本币
        # 大类合并：MHAS 的 harmonized 总额 = doc+hos+den+osrg+fhho(+drug*12)，
        # 故 folk（民间治疗师）必须计入 other，否则 w1-4 会计恒等式破裂；folk 另单列供子分析。
        for cat in CATS:
            raw['cat_'+cat] = pd.to_numeric(
                raw.get('c_'+cat, pd.Series(np.nan, index=raw.index)), errors='coerce')
        if 'c_folk' in raw.columns:
            fk = pd.to_numeric(raw['c_folk'], errors='coerce')
            raw['cat_folk'] = fk
            raw['cat_other'] = raw['cat_other'].fillna(0.0) + fk.fillna(0.0)
        else:
            raw['cat_folk'] = 0.0
        # 覆盖标记：该库该波是否问了此大类
        for cat in CATS + ['folk']:
            raw['avail_'+cat] = int('c_'+cat in raw.columns and raw['c_'+cat].notna().any())
        keep_cols = ['id'] + ['cat_'+x for x in CATS+['folk']] + ['avail_'+x for x in CATS+['folk']]
        b = base[base['wave']==w].copy()
        m = b.merge(raw[keep_cols], on='id', how='left')
        # 未问的分项按 0（与 harmonized 总额定义一致）；已问但缺失按 0 会破坏恒等，单独标记
        for cat in CATS:
            av = m['avail_'+cat].fillna(0).astype(int)
            m['cat_'+cat] = m['cat_'+cat].fillna(0.0)
            m.loc[m['cat_'+cat] < 0, 'cat_'+cat] = 0.0
        m['cat_folk'] = m['cat_folk'].fillna(0.0)
        m['cat_sum_lcu'] = m[['cat_'+x for x in CATS]].sum(axis=1)
        m['exact'] = (np.abs(m['cat_sum_lcu'] - m['oop_annual_lcu']) < 1).astype(int)
        m['resid_lcu'] = m['cat_sum_lcu'] - m['oop_annual_lcu']
        # 覆盖率与恒等
        n = len(m); ne = int(m['exact'].sum())
        cov = {cat: round(100*float((m['cat_'+cat]>0).mean()),1) for cat in CATS}
        chk = dict(db=db, wave=w, n=n, n_exact=ne, exact_pct=round(100*ne/n,2) if n else None,
                   median_ratio=float(np.nanmedian((m['cat_sum_lcu']/m['oop_annual_lcu'].replace(0,np.nan)))),
                   corr=float(m[['cat_sum_lcu','oop_annual_lcu']].corr().iloc[0,1]),
                   median_resid=float(m['resid_lcu'].median()),
                   n_zero_total=int((m['oop_annual_lcu']==0).sum()),
                   **{f'pos_{k}_pct':v for k,v in cov.items()}, secs=round(time.time()-t0,1))
        checks.append(chk)
        log(f"  w{w}: n={n:,} 精确恒等={ne:,} ({chk['exact_pct']}%) 中位比={chk['median_ratio']:.4f} "
            f"corr={chk['corr']:.4f} 中位残差={chk['median_resid']:.1f} | 各类正支出%={cov}")
        # 附加平减后的分项金额
        for cat in CATS+['folk']:
            m[cat+'_2020intl'] = m['cat_'+cat] / m['deflator_2020']
        m['oop_2020intl_from_parts'] = m['cat_sum_lcu'] / m['deflator_2020']
        keep = (['db','wave','year','id','iso3','arth','oop_annual_lcu','oop_2020intl',
                 'hhinc','age','female','educ','married','shlt','adl_any','diabe','hibpe',
                 'stroke','rural','weight','imputed','deflator_2020'] +
                ['cat_'+x for x in CATS+['folk']] + ['avail_'+x for x in CATS+['folk']] +
                [x+'_2020intl' for x in CATS+['folk']] +
                ['cat_sum_lcu','oop_2020intl_from_parts','exact','resid_lcu'])
        frames.append(m[keep])
    conn.close()

D = pd.concat(frames, ignore_index=True)
D.to_csv(os.path.join(OUT, '23_data_components.csv'), index=False, encoding='utf-8-sig',
         float_format='%.6f')
pd.DataFrame(checks).to_csv(os.path.join(OUT, '23_component_check.csv'), index=False,
                            encoding='utf-8-sig', float_format='%.4f')
log(f"\nDONE: 分项数据集 {len(D):,} 行，{D['db'].nunique()} 库，{len(checks)} 个库×波")
log(f"会计恒等总体：{D['exact'].mean()*100:.2f}% 行精确相等；"
    f"仅保留 exact=1 的行进入 A2 结构分解主分析")
log("输出：23_data_components.csv / 23_component_check.csv / 23_component_check.txt")
