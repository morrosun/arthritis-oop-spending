# A1 分析数据集变量字典（`18_data_<db>.csv`）

生成脚本：`18_build_analysis_data.py`（只读抽取）｜审计：`19_audit_join.py`｜生成日期：2026-11-12

## 行与分析单位
一行 = 一个受访者在某一波（`db` + `wave` + `id`）。`(wave,id)` 全局唯一。仅受访者本人 `r` 系列变量，`s` 系列（配偶镜像）一律不用。

## 标识与时间
| 变量 | 定义 |
|---|---|
| `db` | mhas / hrs / share / lasi / charls |
| `wave` | 各库 harmonized 波次；主分析 mhas 1–6、hrs 3–16、share 1/2/5/6、lasi 1；charls 1–4 为扩展库 |
| `year` | 波次调查年份（MHAS 2001/2003/2012/2015/2018/2021；HRS 1992+2(w−1)；SHARE 2004/2007/2013/2015；LASI 2017；CHARLS 2011/2013/2015/2018） |
| `id` | 各库主键：mhas `rahhidnp`、hrs `hhidpn`、share `mergeid`、lasi `prim_key`、charls `id`；亦为聚类稳健 SE 的 cluster 单位 |
| `iso3` | 国家；SHARE 由 `country` 数字编码经 `share_value_labels` 映射为 ISO3，其余库固定 |

## 暴露
| 变量 | 定义 |
|---|---|
| `arth` | `r{w}arthre`，自报 ever-diagnosed 关节炎/风湿，0/1。累计变量（阳性不回落），不能研究缓解，可用于定义新发时点。无法区分 OA / RA / 痛风 / 骨质疏松 |

## 金额与平减
| 变量 | 定义 |
|---|---|
| `oop_annual_lcu` | 年化名义本币自付医疗总额。HRS w3–16 原为「prv 2 yrs」，已 ÷2；其余库 12 个月口径。剔 <0 与 ≥999996 哨兵；0 为真实零支出并保留 |
| `deflator_2020` | `PPP(iso3, year) × CPI_USA(year)/CPI_USA(2020)`；World Bank WDI，`lastupdated 2026-11-11` |
| `oop_2020intl` | `oop_annual_lcu / deflator_2020`，2020 国际元；用于 log-OLS 与 g-computation |
| CHARLS 专有 | 自建总额 = `r{w}oopdoc1m × 12 + r{w}oophos1y + r{w}oopden1y`（w1/w4 无牙科项，按 0）；EOL 反推 harmonized 总额还含**药费**，在世波无该变量，故系统性低估约 1–2%。**不与 harmonized 口径等价** |

> SHARE 金额为**各国本币**，跨国绝对金额不可直接比较；分析含国家固定效应并逐国 PPP 平减。相对效应对库内常数缩放不变。

## 收入、负担与 CHE
| 变量 | 定义 |
|---|---|
| `hhinc` | 家庭总收入，本币年度口径：mhas `h{w}itot`、hrs `h{w}itot`（text，已 cast）、share `hh1itot`(w1) / `hh{w}itothhinc`(w2/5/6)、lasi `hh1itot`、charls `hh{w}itot`。**保留真实负值与大额收入**，不按金额哨兵剔除 |
| `inc_nonpos` | `hhinc <= 0` 标记；这部分人不进入比值结局，须单独描述，不静默删除 |
| `burden_ratio` | `oop_annual_lcu / hhinc`，仅 `hhinc > 0` 时有值 |
| `burden10` / `burden40` | `burden_ratio >= 0.10 / 0.40` 的二值变量（**income-based financial burden，不是 WHO-style CHE**） |
| `ctot` | 家庭消费；mhas 与 share-w1 为**月度**（构造 CHE 时 ×12 年化），charls / lasi 为年度；HRS 无此变量 |
| `che10_cons` | `oop_annual_lcu / (年化 ctot) >= 0.10`；仅 MHAS 6 波、SHARE w1、LASI w1、CHARLS 4 波可得 |
| `miss_ctot` | 消费缺失标记 |

> ⚠️ **SHARE w2/w5/w6 收入口径与 w1 不可比**：同一人 `hh{w}itothhinc / hh1itot` 中位 10.32（w2/w6）、10.69（w5），系变量定义不同。主分析 B10/B40 仅用 SHARE w1；`/10.3178` 校正仅作敏感性，未经官方 codebook 确认。

## 协变量
| 变量 | 定义 |
|---|---|
| `age` | 年龄，主分析限 50–110 |
| `female` | `ragender == 2`（1=male, 2=female） |
| `educ` | 各库教育分类原码（编码数不同：mhas 1–3、hrs 1–5、share 1–3、lasi 0–9、charls 1–10），模型内转 dummy，**不跨库直接比水平** |
| `married` | `mstat ∈ {1,2,3}` |
| `shlt` | 自评健康 1(excellent)–5(poor) |
| `adl_any` | `adl > 0`；mhas/share/lasi 用 `r{w}adla`，hrs 用 `r{w}adl5a`，charls 用 `r{w}adla_c` |
| `diabe` / `hibpe` / `stroke` | 自报 ever-diagnosed 0/1，主模型共病集 |
| `hearte` | 心脏病 0/1；**MHAS w1–3 无此列**（填 0 并置 `miss_hearte`），故不进主模型 |
| `rural` | 城乡；**HRS 无该变量**（填 0 并置 `miss_rural`），模型自动剔除常数列 |
| `weight` / `weight_raw` | `weight` 为按「库×国家」组内均值归一化到 1 的分析权重；`weight_raw` 为原始权重。CHARLS w4 无权重，填 1 |
| `flag` / `imputed` | 金额插补标记及二值化：mhas `flag=1`、hrs `flag>0`、share/lasi `flag ∈ {2,3,5,7}`、charls 无标记 |
| `miss_*` | 对应可选协变量的缺失指示（rural / weight / ctot / country / hearte） |

## 已排除内容
- HRS w2（唯一 12 个月窗、插补率 52%）、SHARE w7（简版问卷 `-4` 63,233 条、患病率异常 52.8%）、CRELES（3 个月口径不相容）。
- 所有金额均不含 `s` 系列（配偶）与家庭层面 `h2oopmd`。
- 建模不做 naïve pooling：按库估计后 DerSimonian-Laird 随机效应合并。
