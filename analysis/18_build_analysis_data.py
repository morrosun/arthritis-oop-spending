# -*- coding: utf-8 -*-
"""方向 A / 任务 10：构建 A1 人-波级分析数据集（只读抽取，落盘 CSV）。
主分析四库 25 波：MHAS w1-6、HRS w3-16、SHARE w1/2/5/6、LASI w1；
扩展库 CHARLS w1-4（自建年化总额，不进主 meta）。
口径要点：
  * HRS w3-16 的 oopmd 为 2 年口径 -> 除以 2；其余库 12 个月口径。
  * 金额剔 <0 与 >=999996 哨兵；收入保留真实负值与大额（不作哨兵剔除）。
  * 主分析仅限受访者本人 r 系列；年龄限 50-110。
  * OOP/家庭收入比值：分母 <=0 记为缺失并单列标记，不静默删除。
  * 平减：World Bank PPP(国,年) x 美国 CPI 定基至 2020 国际元（17_deflators_all.csv）。
  * SHARE 各国金额为本币，按 country -> ISO3 逐国平减；不做跨国家绝对金额 naïve 合并。
输出：18_data_<db>.csv、18_flow.csv/.txt、18_codebook.md。
"""
import os, csv, json, time, psycopg2, pandas as pd
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
TXT = os.path.join(OUT, '18_flow.txt')
META = ('catalog','keys','value_label','variable_label','wave_map','_vl','_hcap_',
        'covid','_eol','_lh_','gvwt','harm_map','_long')

CFG = {
 'mhas': dict(key='rahhidnp', waves=list(range(1,7)), prefix='h_mhas_d_p', iso3='MEX',
   years={1:2001,2:2003,3:2012,4:2015,5:2018,6:2021}, div=lambda w:1.0,
   imp=lambda f: f.eq(1), cols=dict(
    oop='r{w}oopmd1y', flag='r{w}oopmdf1y', arth='r{w}arthre',
    age='r{w}agey', gender='ragender', educ='raeducl', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adla', diabe='r{w}diabe', hibpe='r{w}hibpe',
    stroke='r{w}stroke', itot='h{w}itot', ctot='hh{w}ctot1m',
    rural='h{w}rural', weight='r{w}weight')),
 'hrs': dict(key='hhidpn', waves=list(range(3,17)), prefix='randhrs1992_2022v1_p', iso3='USA',
   years={w:1992+2*(w-1) for w in range(3,17)}, div=lambda w:2.0,
   imp=lambda f: f.gt(0), cols=dict(
    oop='r{w}oopmd', flag='r{w}oopmdf', arth='r{w}arthre',
    age='r{w}agey_b', gender='ragender', educ='raeduc', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adl5a', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke', itot='h{w}itot', weight='r{w}weight')),
 'share': dict(key='mergeid', waves=[1,2,5,6], prefix='gh_share_p', iso3=None,
   years={1:2004,2:2007,5:2013,6:2015}, div=lambda w:1.0,
   imp=lambda f: f.isin([2,3,5,7]), cols=dict(
    oop='r{w}oopmd1y', flag='r{w}oopmdf1y', arth='r{w}arthre',
    age='r{w}agey', gender='ragender', educ='raeducl', mstat='r{w}mstat',
    shlt='r{w}shlt', adl='r{w}adla', diabe='r{w}diabe', hibpe='r{w}hibpe',
    hearte='r{w}hearte', stroke='r{w}stroke',
    itot=['hh{w}itothhinc','hh1itot'], ctot='hh1ctot1m',
    rural='h{w}rural', weight='r{w}weight', country='country')),
 'lasi': dict(key='prim_key', waves=[1], prefix='gh_lasi_p', iso3='IND',
   years={1:2017}, div=lambda w:1.0,
   imp=lambda f: f.isin([2,3,5,7]), cols=dict(
    oop='r1oopmd1y_l', flag='r1oopmdf1y_l', arth='r1arthre',
    age='r1agey', gender='ragender', educ='raeduc_l', mstat='r1mstat',
    shlt='r1shlt', adl='r1adla', diabe='r1diabe', hibpe='r1hibpe',
    hearte='r1hearte', stroke='r1stroke', itot='hh1itot', ctot='hh1ctot',
    rural=['hh1rural','h1rural'], weight=['r1mweight','indiaindividualweight'])),
 'charls': dict(key='id', waves=[1,2,3,4], prefix='harm_h_charls_d_data_p', iso3='CHN',
   years={1:2011,2:2013,3:2015,4:2018}, div=lambda w:1.0, selfbuilt=True,
   imp=None, cols=dict(
    oopdoc='r{w}oopdoc1m', oophos='r{w}oophos1y', oopden=['r{w}oopden1y'],
    arth='r{w}arthre', age='r{w}agey', gender='ragender', educ='raeduc_c',
    mstat='r{w}mstat', shlt=['r{w}shlt','r{w}shlta'], adl='r{w}adla_c',
    diabe='r{w}diabe', hibpe='r{w}hibpe', hearte='r{w}hearte', stroke='r{w}stroke',
    itot='hh{w}itot', ctot='hh{w}ctot', rural='r{w}rural2', weight=['r{w}mweight'])),
}
SHARE_ISO = {11:'AUT',12:'DEU',13:'SWE',14:'NLD',15:'ESP',16:'ITA',17:'FRA',18:'DNK',
 19:'GRC',20:'CHE',23:'BEL',25:'ISR',28:'CZE',29:'POL',30:'IRL',31:'LUX',32:'HUN',
 33:'PRT',34:'SVN',35:'EST',47:'HRV',48:'LTU',51:'BGR',53:'CYP',55:'FIN',57:'LVA',
 59:'MLT',61:'ROU',63:'SVK'}
CORE = ['age','gender','educ','mstat','shlt','adl','diabe','hibpe','stroke','itot']

lines = []
def log(s=''):
    print(s); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def ex(alias, col):
    return sql.SQL("NULLIF({}.{}::text, '')::numeric").format(
        sql.Identifier(alias), sql.Identifier(col))

log("方向 A / 任务 10：A1 人-波级分析数据集构建｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("只读抽取；主分析四库 25 波 + CHARLS 扩展 4 波；金额年化、平减、负担比在 Python 层构造。\n")

# 平减表
DEF = pd.read_csv(os.path.join(OUT, '17_deflators_all.csv'))
DEFMAP = {(r.iso3, int(r.year)): r.deflator_to_2020 for r in DEF.itertuples()
          if pd.notna(r.deflator_to_2020)}
log(f"平减表载入：{len(DEFMAP)} 个 (ISO3, 年) 可用 deflator")

flow = []
for db, cfg in CFG.items():
    log(f"\n########## {db} ##########  waves={cfg['waves']}")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='300s'")
    cur.execute("""SELECT table_name, column_name FROM information_schema.columns
                   WHERE table_schema='public' ORDER BY table_name, ordinal_position""")
    colmap = {}
    for t, col in cur.fetchall():
        if any(m in t.lower() for m in META):
            continue
        colmap.setdefault(col.lower(), []).append(t)
    def pick(name):
        cand = colmap.get(name.lower()) or []
        pref = [t for t in cand if cfg['prefix'] in t]
        return (pref or cand or [None])[0]

    out_csv = os.path.join(OUT, f'18_data_{db}.csv')
    if os.path.exists(out_csv):
        os.remove(out_csv)
    header = True
    for w in cfg['waves']:
        t0 = time.time()
        # 解析本波列名 -> 表
        res = {}
        for concept, tpl in cfg['cols'].items():
            for t in (tpl if isinstance(tpl, list) else [tpl]):
                name = t.format(w=w)
                tb = pick(name)
                if tb:
                    res[concept] = (name, tb); break
        # 驱动表 = oop（或 CHARLS 的 oopdoc）所在表
        drv_concept = 'oop' if not cfg.get('selfbuilt') else 'oopdoc'
        if drv_concept not in res:
            log(f"  w{w}: 缺 {drv_concept} 列 -> SKIP"); continue
        drv_table = res[drv_concept][1]
        tables, alias = [drv_table], {drv_table: 'a0'}
        for concept, (col, tb) in res.items():
            if tb not in alias:
                alias[tb] = f'a{len(tables)}'; tables.append(tb)
        selects = [sql.SQL("{}.{} AS id").format(sql.Identifier(alias[drv_table]),
                                                  sql.Identifier(cfg['key']))]
        for concept, (col, tb) in res.items():
            selects.append(sql.SQL("{e} AS {c}").format(e=ex(alias[tb], col),
                                                         c=sql.Identifier(concept)))
        joins = [sql.SQL("FROM public.{t} {a}").format(t=sql.Identifier(drv_table),
                                                        a=sql.Identifier('a0'))]
        for tb in tables[1:]:
            joins.append(sql.SQL("LEFT JOIN public.{t} {a} USING ({k})").format(
                t=sql.Identifier(tb), a=sql.Identifier(alias[tb]),
                k=sql.Identifier(cfg['key'])))
        q = sql.SQL("SELECT {s} {j}").format(s=sql.SQL(', ').join(selects),
                                             j=sql.SQL(' ').join(joins))
        try:
            cur.execute(q)
            df = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
        except Exception as e:
            conn.rollback()
            log(f"  w{w}: SQL 失败 {type(e).__name__} {str(e)[:200]}")
            continue
        n_join = len(df)
        f = dict(db=db, wave=w, year=cfg['years'].get(w), n_join=n_join,
                 missing_cols=','.join(sorted(set(cfg['cols']) - set(res))))
        # ---- 金额 ----
        if cfg.get('selfbuilt'):
            for cc in ['oopdoc','oophos','oopden']:
                if cc not in df: df[cc] = 0.0
                df[cc] = pd.to_numeric(df[cc], errors='coerce').fillna(0.0)
            df['oop'] = 12*df['oopdoc'] + df['oophos'] + df['oopden']
            df['flag'] = float('nan')
        div = cfg['div'](w)
        oop = pd.to_numeric(df['oop'], errors='coerce') / div
        df['oop_annual_lcu'] = oop.where((oop >= 0) & (oop < 999996))
        f['n_oop_valid'] = int(df['oop_annual_lcu'].notna().sum())
        df = df[df['oop_annual_lcu'].notna()].copy()   # 无有效金额的行不进分析集
        # ---- 暴露与人口学 ----
        df['arth'] = pd.to_numeric(df['arth'], errors='coerce')
        df = df[df['arth'].isin([0,1])].copy()
        f['n_arth'] = len(df)
        for cc in ['age','gender','educ','mstat','shlt','adl','diabe','hibpe','stroke',
                   'itot','ctot','rural','weight','country','flag','hearte']:
            if cc not in df: df[cc] = float('nan')
            df[cc] = pd.to_numeric(df[cc], errors='coerce')
        df = df[(df['age'] >= 50) & (df['age'] <= 110)].copy()
        f['n_age50_110'] = len(df)
        # 共病/人口学完整集
        df['female'] = (df['gender'] == 2).astype(float)
        df.loc[df['gender'].isna(), 'female'] = float('nan')
        df['married'] = df['mstat'].isin([1,2,3]).astype(float)
        df.loc[df['mstat'].isna(), 'married'] = float('nan')
        df['adl_any'] = (df['adl'] > 0).astype(float)
        df.loc[df['adl'].isna(), 'adl_any'] = float('nan')
        # 可选协变量缺失不做删除，改中性填充 + 标记
        for cc, fill in [('rural',0),('weight',1.0),('ctot',float('nan')),
                         ('country',0),('hearte',0)]:
            df['miss_'+cc] = df[cc].isna().astype(int)
            df[cc] = df[cc].fillna(fill)
        core = ['age','female','educ','mstat','shlt','adl_any','diabe','hibpe','stroke','itot']
        df = df.dropna(subset=core).copy()
        f['n_complete_core'] = len(df)
        # ---- 负担比（分母 <=0 记缺失）----
        inc = df['itot']
        df['hhinc'] = inc
        df['inc_nonpos'] = (inc <= 0).astype(int)
        denom = inc.where(inc > 0)
        df['burden_ratio'] = df['oop_annual_lcu'] / denom
        df['burden10'] = (df['burden_ratio'] >= 0.10).astype(float)
        df['burden40'] = (df['burden_ratio'] >= 0.40).astype(float)
        df.loc[df['burden_ratio'].isna(), ['burden10','burden40']] = float('nan')
        # ---- 消费 CHE 敏感性（仅可得波次）----
        # SHARE 的 hh1ctot1m 是 w1 月度消费，不能挂到 w2/w5/w6 当分母
        if db == 'share' and w != 1:
            df['ctot'] = float('nan'); df['miss_ctot'] = 1
        ctot = df['ctot']
        chem = ctot.where(ctot > 0)
        if db in ('mhas', 'share'): chem = chem * 12   # 月度消费 -> 年化
        df['che10_cons'] = (df['oop_annual_lcu'] / chem >= 0.10).astype(float)
        df.loc[chem.isna(), 'che10_cons'] = float('nan')
        # ---- 插补标记 ----
        df['imputed'] = (cfg['imp'](df['flag']).astype(int)
                         if cfg['imp'] is not None else 0)
        # ---- 国家与平减 ----
        if db == 'share':
            df['iso3'] = df['country'].round().astype(int).map(SHARE_ISO)
        else:
            df['iso3'] = cfg['iso3']
        df['wave'] = w; df['year'] = cfg['years'].get(w); df['db'] = db
        df['deflator_2020'] = [DEFMAP.get((i, y)) for i, y in zip(df['iso3'], df['year'])]
        f['n_deflator_covered'] = int(df['deflator_2020'].notna().sum())
        df['oop_2020intl'] = df['oop_annual_lcu'] / df['deflator_2020']
        df['hhinc_2020intl'] = df['hhinc'] / df['deflator_2020']
        # ---- 权重归一化（按 库×国家 组内均值 1）----
        df['weight_raw'] = df['weight'].where(df['weight'] > 0)
        grp = df.groupby('iso3', dropna=False)['weight_raw'].transform('mean')
        df['weight'] = (df['weight_raw'] / grp).fillna(1.0)
        # ---- 输出 ----
        keep = ['db','wave','year','id','iso3','arth','oop_annual_lcu','oop_2020intl',
                'hhinc','hhinc_2020intl','inc_nonpos','burden_ratio','burden10','burden40',
                'che10_cons','age','female','educ','married','shlt','adl_any',
                'diabe','hibpe','stroke','hearte','rural','weight','weight_raw',
                'flag','imputed','deflator_2020','ctot',
                'miss_rural','miss_weight','miss_ctot','miss_country','miss_hearte']
        for k in keep:
            if k not in df: df[k] = float('nan')
        df[keep].to_csv(out_csv, mode='a', header=header, index=False,
                        encoding='utf-8-sig', float_format='%.6f')
        header = False
        f['n_final'] = len(df)
        f['n_arth1'] = int((df['arth'] == 1).sum())
        f['n_burden_valid'] = int(df['burden_ratio'].notna().sum())
        f['n_che_cons_valid'] = int(df['che10_cons'].notna().sum())
        f['secs'] = round(time.time()-t0, 1)
        flow.append(f)
        log(f"  w{w} ({f['year']}): join={n_join:,} -> oop有效={f['n_oop_valid']:,} "
            f"-> arth={f['n_arth']:,} -> 年龄={f['n_age50_110']:,} "
            f"-> 完整核心={f['n_complete_core']:,} = 最终 | arth+={f['n_arth1']:,} "
            f"负担比可算={f['n_burden_valid']:,} 消费CHE可算={f['n_che_cons_valid']:,} "
            f"平减覆盖={f['n_deflator_covered']:,} | 缺列=[{f['missing_cols']}] [{f['secs']}s]")
    conn.close()

with open(os.path.join(OUT, '18_flow.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(flow[0].keys()))
    wr.writeheader(); wr.writerows(flow)
log(f"\nDONE: {len(flow)} 波，最终人波 = {sum(x['n_final'] for x in flow):,}")
