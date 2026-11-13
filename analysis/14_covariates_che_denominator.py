# -*- coding: utf-8 -*-
"""点查 A1 建模所需协变量，尤其是 CHE 的家庭消费分母是否可得。
只读。结果落盘 14_covariates_che_denominator.txt / .json。"""
import os, json, re, psycopg2
from psycopg2 import sql

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
CONN = "host=%s port=%s user=%s password=%s" % (
    os.environ.get("OOPE_DB_HOST", "localhost"),
    os.environ.get("OOPE_DB_PORT", "5432"),
    os.environ.get("OOPE_DB_USER", "postgres"),
    os.environ.get("OOPE_DB_PASSWORD", ""))
DBS = ['mhas', 'hrs', 'share', 'lasi', 'charls']

GROUPS = {
 'CHE分母_消费': ['cons', 'ctot', 'hsexp', 'hexp', 'pce', 'foodexp', 'hhexp', 'expend'],
 'CHE分母_收入': ['itot', 'hhtot', 'hhinc', 'income', 'incw', 'earn', 'wealth', 'asset'],
 '人口学': ['agey', 'age', 'gender', 'female', 'sex', 'educ', 'married', 'mstat', 'couple'],
 '健康': ['shlt', 'srh', 'adl', 'iadl', 'bmi', 'cesd', 'diabe', 'hibpe', 'cancere', 'hearte', 'stroke'],
 '保险': ['insur', 'cover', 'medicaid', 'medicare', 'hi'],
 '权重': ['weight', 'wght', 'wgt'],
 '地区': ['country', 'urban', 'rural', 'region', 'state'],
}

lines = []
def log(s=''):
    print(s); lines.append(str(s))
report = {}

for db in DBS:
    log(f"\n########## {db} ##########")
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("SET statement_timeout='120s'")
    cur.execute("""SELECT DISTINCT column_name FROM information_schema.columns
                   WHERE table_schema='public'""")
    cols = sorted({r[0].lower() for r in cur.fetchall()})
    dbres = {}
    for g, kws in GROUPS.items():
        hits = {}
        for kw in kws:
            h = [c for c in cols if kw in c]
            # 过滤明显的干扰（如 'agey' 命中 'manage' 之类），保留 r/s + 波次 或 无前缀
            h = [c for c in h if re.match(r'^[rsh]\d*[a-z0-9_]*$', c) or '_' not in c][:18]
            if h: hits[kw] = h
        dbres[g] = hits
        log(f"  [{g}] " + '; '.join(f"{k}:{','.join(v[:10])}" for k, v in hits.items()))
    report[db] = dbres
    conn.close()

# 对 CHE 分母候选做非空行数核验（挑最可能的几个）
log("\n########## CHE 分母候选：实库非空行数 ##########")
CAND = {
 'mhas':  ['r1hsexp1y','r1ctot','r1itot','r1hhtot','r1hhinc','r1cons1y','r1foodexp'],
 'hrs':   ['r1hsexp','r1ctot','r1itot','r1hhtot','r1atotb','r1atotf','h1ctot'],
 'share': ['r1hsexp','r1ctot','r1itot','r1hhtot','r1hhcons','r1cons','r1thinc'],
 'lasi':  ['r1hsexp','r1ctot','r1itot','r1hhtot','r1hhcons','r1cons','r1mpce'],
 'charls':['r1hsexp','r1ctot','r1itot','r1hhtot','r1hhcons','r1cons','r1pce'],
}
che = {}
for db, cands in CAND.items():
    conn = psycopg2.connect(CONN + " dbname=" + db)
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT column_name FROM information_schema.columns
                   WHERE table_schema='public'""")
    cols = {r[0].lower() for r in cur.fetchall()}
    actual = [c for c in cands if c in cols]
    # 补充：自动找所有含 cons/ctot/hsexp/itot/hhtot 的 r 系列变量
    auto = sorted([c for c in cols if re.match(r'^r\d+(cons|ctot|hsexp|itot|hhtot|hhcons|pce|thinc|atot)', c)])[:25]
    log(f"  {db}: 指定候选命中={actual} | 自动发现={auto[:20]}")
    che[db] = {'specified': actual, 'auto': auto}
    # 对自动发现的前 8 个查非空行数
    for v in auto[:8]:
        cur.execute("""SELECT table_name FROM information_schema.columns
                       WHERE table_schema='public' AND column_name=%s LIMIT 1""", (v,))
        r = cur.fetchone()
        if not r: continue
        try:
            cur.execute(sql.SQL('SELECT count({c}), min({c})::float8, max({c})::float8 FROM public.{t}').format(
                c=sql.Identifier(v), t=sql.Identifier(r[0])))
            n, mn, mx = cur.fetchone()
            log(f"     {v} [{r[0]}]: 非空={n:,} min={mn} max={mx}")
            che[db][v] = {'table': r[0], 'nonnull': n, 'min': mn, 'max': mx}
        except Exception as e:
            conn.rollback(); log(f"     {v}: 统计失败 {str(e)[:100]}")
    conn.close()
report['_che_denominator'] = che

with open(os.path.join(OUT, '14_covariates_che_denominator.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
with open(os.path.join(OUT, '14_covariates_che_denominator.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
log("\nDONE -> 14_covariates_che_denominator.txt / .json")
