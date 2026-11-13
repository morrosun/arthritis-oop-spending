# -*- coding: utf-8 -*-
"""方向 A / 任务 9b：一次批量抓取 World Bank 全部国家 PPP + CPI，构建完整平减表。
与 17_fetch_deflators.py 的逐国结果交叉复核（MEX/USA/CHN 应完全一致）。
输出：17_wb_bulk_<ind>.json（原始应答精简）、17_deflators_all.csv/json、17b_run.txt。
口径：amount_2020Intl$ = amount_nominal_LCU / [PPP(iso,y) * CPI_USA(y)/CPI_USA(2020)]
"""
import os, json, csv, time, urllib.request, ssl

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
TXT = os.path.join(OUT, '17b_run.txt')
URL = ("https://api.worldbank.org/v2/country/all/indicator/{ind}"
       "?format=json&date=1992:2023&per_page=20000")
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
lines = []
def log(s=''):
    print(s); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def fetch(ind, tries=4, timeout=90):
    last = ''
    for k in range(tries):
        try:
            req = urllib.request.Request(URL.format(ind=ind), headers={'User-Agent': 'Mozilla/5.0'})
            r = urllib.request.urlopen(req, timeout=timeout, context=CTX)
            o = json.loads(r.read().decode('utf-8'))
            if not isinstance(o, list) or len(o) < 2 or o[1] is None:
                last = f'bad payload {str(o)[:120]}'
            else:
                out = {}
                for d in o[1]:
                    iso = d.get('countryiso3code')
                    if iso:
                        out.setdefault(iso, {})[int(d['date'])] = d['value']
                return o[0].get('lastupdated'), out, None
        except Exception as e:
            last = f'{type(e).__name__}: {str(e)[:120]}'
        time.sleep(2)
    return None, None, last

log("方向 A / 任务 9b：World Bank 全国家 PPP/CPI 批量抓取｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
raw = {}
for ind in ['PA.NUS.PPP', 'FP.CPI.TOTL']:
    t0 = time.time()
    lu, d, err = fetch(ind)
    if d is None:
        log(f"  {ind}: FAIL {err}"); continue
    raw[ind] = dict(lastupdated=lu, data=d)
    with open(os.path.join(OUT, '17_wb_bulk_' + ind.replace('.', '_') + '.json'),
              'w', encoding='utf-8') as f:
        json.dump(dict(lastupdated=lu, data=d), f, ensure_ascii=False)
    log(f"  {ind}: OK 国家={len(d)} 年份=1992-2023 lastupdated={lu} [{time.time()-t0:.1f}s]")

ppp = raw.get('PA.NUS.PPP', {}).get('data', {})
cpi = raw.get('FP.CPI.TOTL', {}).get('data', {})
usa = cpi.get('USA', {})
base = usa.get(2020)
log(f"\n美国 CPI(2020) 基准 = {base} ｜有 PPP 国家数 = {len(ppp)}")

def interp(vals, y):
    if vals.get(y) is not None:
        return float(vals[y]), False
    ys = sorted(k for k, v in vals.items() if v is not None)
    if not ys or y < ys[0] or y > ys[-1]:
        return None, True
    lo = max(k for k in ys if k < y); hi = min(k for k in ys if k > y)
    return float(vals[lo]) + (float(vals[hi]) - float(vals[lo])) * (y - lo) / (hi - lo), True

rows = []
for iso in sorted(ppp):
    for y in range(1992, 2024):
        p, pi = interp(ppp[iso], y)
        cu, _ = interp(usa, y)
        lc, lci = interp(cpi.get(iso, {}), y)
        d = p * cu / base if (p and cu and base) else None
        rows.append(dict(iso3=iso, year=y,
                         ppp_lcu_per_intl=round(p, 6) if p else None,
                         ppp_interpolated=int(pi),
                         cpi_local=round(lc, 4) if lc else None,
                         cpi_local_interpolated=int(lci),
                         cpi_usa=round(cu, 4) if cu else None,
                         deflator_to_2020=round(d, 6) if d else None))
with open(os.path.join(OUT, '17_deflators_all.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    wr.writeheader(); wr.writerows(rows)
with open(os.path.join(OUT, '17_deflators_all.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(source='World Bank WDI API (country=all)',
                   indicators=['PA.NUS.PPP','FP.CPI.TOTL'],
                   fetched=time.strftime('%Y-%m-%d %H:%M:%S'),
                   lastupdated={k: v['lastupdated'] for k, v in raw.items()},
                   base_year=2020, cpi_usa_2020=base, nrows=len(rows)), f, indent=1)
log(f"DONE: {len(rows)} 行，deflator 可用 {sum(1 for r in rows if r['deflator_to_2020'])} 行")

# 与逐国抓取结果交叉复核
import collections
ref = {}
p1 = os.path.join(OUT, '17_deflators.csv')
if os.path.exists(p1):
    with open(p1, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['ppp_lcu_per_intl']:
                ref[(r['iso3'], int(r['year']))] = float(r['ppp_lcu_per_intl'])
    bulk = {(r['iso3'], r['year']): r['ppp_lcu_per_intl'] for r in rows
            if r['ppp_lcu_per_intl'] is not None}
    diffs = [(k, ref[k], bulk.get(k)) for k in ref
             if k in bulk and abs(ref[k] - bulk[k]) > 1e-4]
    log(f"交叉复核：逐国表 {len(ref)} 个 (国家,年) 值；与批量表不一致 = {len(diffs)} 个")
    if diffs:
        log("  不一致样例: " + str(diffs[:8]))
