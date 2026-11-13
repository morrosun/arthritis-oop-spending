# -*- coding: utf-8 -*-
"""方向 A / 任务 9：拉取 World Bank PPP + CPI，构建本币 -> 2020 国际元平减表。
数据源：World Bank WDI API（PA.NUS.PPP = PPP conversion factor, LCU per international $；
        FP.CPI.TOTL = Consumer price index, 2010=100，用美国 CPI 作国际元定基）。
口径：amount_2020Intl$ = amount_nominal_LCU / [PPP(iso,y) * CPI_USA(y)/CPI_USA(2020)]
      —— 先按当年 PPP 换成当年国际元，再用美国 CPI 定基到 2020 年。
策略：增量落盘（每完成一个 国家×指标 立即 append），短超时 + 重试，前台运行。
输出：17_wb_raw.jsonl（原始应答）、17_deflators.csv、17_deflators.txt、17_deflators.json。
用法：python 17_fetch_deflators.py [额外ISO3 ...]
"""
import os, sys, json, csv, time, urllib.request, ssl

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OOPE_OUT_DIR", os.path.join(os.path.dirname(_HERE), "outputs"))
RAW = os.path.join(OUT, '17_wb_raw.jsonl')
TXT = os.path.join(OUT, '17_deflators.txt')
BASE = ("https://api.worldbank.org/v2/country/{iso}/indicator/{ind}"
        "?format=json&date=1992:2023&per_page=100")
IND = ['PA.NUS.PPP', 'FP.CPI.TOTL']
DEFAULT_ISO = ['MEX', 'USA', 'IND', 'CHN']
ISO = DEFAULT_ISO + [x.upper() for x in sys.argv[1:] if x.upper() not in DEFAULT_ISO]
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

lines = []
def log(s=''):
    print(s); lines.append(str(s))
    with open(TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def fetch(iso, ind, tries=4, timeout=12):
    url = BASE.format(iso=iso, ind=ind)
    last = ''
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            r = urllib.request.urlopen(req, timeout=timeout, context=CTX)
            obj = json.loads(r.read().decode('utf-8'))
            if not isinstance(obj, list) or len(obj) < 2 or obj[1] is None:
                last = f'bad payload: {str(obj)[:120]}'
            else:
                return obj[0].get('lastupdated'), {int(d['date']): d['value'] for d in obj[1]}, None
        except Exception as e:
            last = f'{type(e).__name__}: {str(e)[:100]}'
        time.sleep(1.2)
    return None, None, last

log("方向 A / 任务 9：World Bank WDI 平减因子抓取｜" + time.strftime('%Y-%m-%d %H:%M:%S'))
log("指标 PA.NUS.PPP / FP.CPI.TOTL｜年份 1992-2023｜国家 " + ', '.join(ISO))
log("口径见脚本文件头；每次成功后立即增量写盘。\n")

data = {}
for iso in ISO:
    for ind in IND:
        t0 = time.time()
        lu, vals, err = fetch(iso, ind)
        if vals is None:
            log(f"  {iso} {ind}: FAIL {err}  [{time.time()-t0:.1f}s]")
            continue
        data[(iso, ind)] = dict(lastupdated=lu, values=vals)
        with open(RAW, 'a', encoding='utf-8') as f:
            f.write(json.dumps(dict(iso=iso, indicator=ind, lastupdated=lu,
                                    values=vals, fetched=time.strftime('%Y-%m-%d %H:%M:%S')),
                               ensure_ascii=False) + '\n')
        nz = sum(1 for v in vals.values() if v is not None)
        log(f"  {iso} {ind}: OK 年份={len(vals)} 非空={nz} lastupdated={lu} [{time.time()-t0:.1f}s]")

# 定基与插值
usa_cpi = data.get(('USA', 'FP.CPI.TOTL'), {}).get('values', {})
base = usa_cpi.get(2020)
log(f"\n美国 CPI(2020) 基准 = {base}")
if not base:
    log("!! 缺美国 CPI 2020，无法定基；仅输出 PPP 原值。")

def series(iso, ind):
    return data.get((iso, ind), {}).get('values', {})

def interp(vals, y):
    """相邻年份线性插值；返回 (value, is_interpolated)。超范围返回 (None, True)。"""
    if vals.get(y) is not None:
        return float(vals[y]), False
    ys = sorted(k for k, v in vals.items() if v is not None)
    if not ys or y < ys[0] or y > ys[-1]:
        return None, True
    lo = max(k for k in ys if k < y); hi = min(k for k in ys if k > y)
    v = float(vals[lo]) + (float(vals[hi]) - float(vals[lo])) * (y - lo) / (hi - lo)
    return v, True

rows = []
for iso in ISO:
    ppp_s, cpi_s = series(iso, 'PA.NUS.PPP'), series(iso, 'FP.CPI.TOTL')
    if not ppp_s:
        log(f"  {iso}: 无 PPP 数据，跳过"); continue
    for y in range(1992, 2024):
        p, pi = interp(ppp_s, y)
        cu, cui = interp(usa_cpi, y)
        d = (p * cu / base) if (p and cu and base) else None
        lc, lci = interp(cpi_s, y)
        rows.append(dict(iso3=iso, year=y,
                         ppp_lcu_per_intl=round(p, 6) if p else None,
                         ppp_interpolated=int(pi),
                         cpi_local=round(lc, 4) if lc else None,
                         cpi_local_interpolated=int(lci),
                         cpi_usa=round(cu, 4) if cu else None,
                         deflator_to_2020=round(d, 6) if d else None))

with open(os.path.join(OUT, '17_deflators.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    wr.writeheader(); wr.writerows(rows)
with open(os.path.join(OUT, '17_deflators.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(source='World Bank WDI API', indicators=IND,
                   fetched=time.strftime('%Y-%m-%d %H:%M:%S'),
                   lastupdated={f'{k[0]}|{k[1]}': v['lastupdated'] for k, v in data.items()},
                   base_year=2020, rows=rows), f, ensure_ascii=False, indent=1)
ok = sum(1 for r in rows if r['deflator_to_2020'])
log(f"\nDONE: {len(rows)} 行，其中 deflator 可用 {ok} 行 -> 17_deflators.csv / .json")
