"""Case File Earth - deterministic trend analysis (Apache 2.0).
Input: NASA POWER monthly point data (MERRA-2 based), Santiago -33.45,-70.67.
Run: python analysis/trend_analysis.py data/data_power_santiago_1981_2025.csv
"""
import sys, json, csv, math
import numpy as np
from scipy import stats
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def mk(y):
    """Mann-Kendall (tie-corrected, continuity corrected) + Sen slope per step + 95% CI of slope."""
    y = np.asarray(y, float); n = len(y)
    S = sum(np.sign(y[j]-y[i]) for i in range(n-1) for j in range(i+1, n))
    _, c = np.unique(y, return_counts=True)
    var = (n*(n-1)*(2*n+5) - sum(t*(t-1)*(2*t+5) for t in c))/18
    z = 0 if S == 0 else (S-np.sign(S))/math.sqrt(var)
    p = 2*(1-stats.norm.cdf(abs(z)))
    sl = np.array([(y[j]-y[i])/(j-i) for i in range(n-1) for j in range(i+1, n)])
    sl.sort(); N = len(sl)
    Ca = stats.norm.ppf(0.975)*math.sqrt(var)
    lo = sl[max(int(math.floor((N-Ca)/2)), 0)]; hi = sl[min(int(math.ceil((N+Ca)/2)), N-1)]
    return dict(n=n, S=float(S), z=float(z), p=float(p), sen=float(np.median(sl)), sen_lo=float(lo), sen_hi=float(hi))

def pf(p):
    return "p<0.001" if p < 0.001 else f"p={p:.3f}"

def verdict(p):
    return "strong evidence" if p < 0.05 else ("weak evidence, trend not proven" if p < 0.15 else "no proven trend")

rows = list(csv.DictReader(open(sys.argv[1])))
rows = [r for r in rows if 1 <= int(r["month"]) <= 12]  # drop YYYY13 annual keys
Y = np.array([int(r["year"]) for r in rows]); M = np.array([int(r["month"]) for r in rows])
D = np.array([int(r["days_in_month"]) for r in rows])
P = np.array([float(r["PRECTOTCORR_mm_per_day"]) for r in rows]) * D   # mm/month
T = np.array([float(r["T2M_C"]) for r in rows])
years = sorted(set(Y)); assert len(rows) == 540 and len(years) == 45

def annual(v, agg):
    return np.array([agg(v[Y == y]) for y in years])
def seasonal(v, months, agg):
    out = []
    for y in years:
        if months == (12, 1, 2):  # DJF assigned to the year of Jan/Feb; incomplete first year dropped
            if y == years[0]: continue
            m = ((Y == y-1) & (M == 12)) | ((Y == y) & np.isin(M, [1, 2]))
        else:
            m = (Y == y) & np.isin(M, months)
        out.append(agg(v[m]))
    return np.array(out)

res = {"meta": dict(source="NASA POWER monthly point API (MERRA-2 / POWER), PRECTOTCORR and T2M",
      point=[-33.45, -70.67], period="1981-2025", months=int(len(rows)),
      precip_mm_month="PRECTOTCORR mm/day x days in month",
      verdict_rule="p<0.05 strong; 0.05-0.15 weak/not proven; else no proven trend")}
seasons = {"Annual": None, "DJF (summer)": (12,1,2), "MAM (autumn)": (3,4,5), "JJA (winter)": (6,7,8), "SON (spring)": (9,10,11)}
out = {}
for var, v, agg, unit in [("precip", P, np.sum, "mm"), ("temp", T, np.mean, "C")]:
    out[var] = {}
    for name, mo in seasons.items():
        if mo is None: a = annual(v, agg); yrs = years
        else:
            a = seasonal(v, mo, agg if var == "temp" or mo != None else agg); yrs = years if mo != (12,1,2) else years[1:]
            if var == "precip": a = seasonal(v, mo, np.sum)
        r = mk(a); r["sen_per_decade"] = r["sen"]*10; r["ci_per_decade"] = [r["sen_lo"]*10, r["sen_hi"]*10]
        ols = stats.linregress(yrs, a); r["ols_per_decade"] = ols.slope*10; r["ols_p"] = ols.pvalue
        r["mean"] = float(np.mean(a)); r["rel_change_pct_per_decade"] = r["sen_per_decade"]/np.mean(a)*100
        r["verdict"] = verdict(r["p"]); r["unit"] = unit
        # lag-1 autocorrelation of detrended series (caveat for MK)
        res_ = a - (ols.intercept + ols.slope*np.array(yrs)); r["lag1_autocorr"] = float(np.corrcoef(res_[:-1], res_[1:])[0,1])
        out[var][name] = r
# period comparison (control for "one wet winter"): 1981-2010 vs 2011-2025 annual precip
a = annual(P, np.sum); A, B = a[:30], a[30:]
tt = stats.ttest_ind(A, B, equal_var=False); mw = stats.mannwhitneyu(A, B)
out["period_compare_precip"] = dict(mean_1981_2010=float(A.mean()), mean_2011_2025=float(B.mean()),
    diff_mm=float(B.mean()-A.mean()), diff_pct=float((B.mean()/A.mean()-1)*100), welch_p=float(tt.pvalue), mannwhitney_p=float(mw.pvalue))
# deseasonalised monthly anomalies, Mann-Kendall (pooled; autocorrelated, indicative only)
anP = P.copy(); anT = T.copy()
for m in range(1, 13):
    anP[M == m] -= P[M == m].mean(); anT[M == m] -= T[M == m].mean()
out["monthly_anomaly_mk"] = {"precip": mk(anP) | {"verdict": verdict(mk(anP)["p"])}, "temp": mk(anT) | {"verdict": verdict(mk(anT)["p"])}}
# driest / wettest years
order = np.argsort(a)
out["driest_years"] = [(int(years[i]), round(float(a[i]), 1)) for i in order[:5]]
out["wettest_years"] = [(int(years[i]), round(float(a[i]), 1)) for i in order[-5:][::-1]]
res["results"] = out
json.dump(res, open("results/results.json", "w"), indent=2)

# charts
x = np.array(years); ap = annual(P, np.sum); at = annual(T, np.mean)
sp = stats.linregress(x, ap); r = out["precip"]["Annual"]
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(x, ap, color=["#c0392b" if v < ap.mean() else "#2e86c1" for v in ap])
ax.axhline(ap.mean(), color="k", ls="--", lw=1, label=f"mean {ap.mean():.0f} mm")
ax.plot(x, np.median(ap - r["sen"]*(x-x[0])) + r["sen"]*(x-x[0]), color="k", lw=2, label=f"Sen slope {r['sen_per_decade']:+.1f} mm/decade ({pf(r['p'])})")
ax.set_title("Annual precipitation, Santiago grid point (NASA POWER), 1981-2025"); ax.set_ylabel("mm/year"); ax.legend()
fig.tight_layout(); fig.savefig("charts/01_annual_precip.png", dpi=150); plt.close(fig)
fig, ax = plt.subplots(figsize=(9, 4.5)); r = out["temp"]["Annual"]
ax.plot(x, at, "o-", color="#e67e22"); ax.plot(x, np.median(at - r["sen"]*(x-x[0])) + r["sen"]*(x-x[0]), "k", lw=2,
    label=f"Sen slope {r['sen_per_decade']:+.2f} C/decade ({pf(r['p'])})")
ax.set_title("Control variable: annual mean temperature T2M, same point"); ax.set_ylabel("deg C"); ax.legend()
fig.tight_layout(); fig.savefig("charts/02_annual_temp_control.png", dpi=150); plt.close(fig)
fig, ax = plt.subplots(figsize=(9, 4.5)); names = list(seasons); 
vals = [out["precip"][n]["rel_change_pct_per_decade"] for n in names]; ps = [out["precip"][n]["p"] for n in names]
ax.bar(names, vals, color=["#2e86c1" if p < 0.05 else "#aab7b8" for p in ps])
for i, (v, p) in enumerate(zip(vals, ps)): ax.text(i, v, pf(p), ha="center", va="bottom" if v >= 0 else "top")
ax.axhline(0, color="k", lw=1); ax.set_ylabel("% of mean per decade (Sen)"); ax.set_title("Precipitation change by season (blue = p<0.05)")
fig.tight_layout(); fig.savefig("charts/03_seasonal_change.png", dpi=150); plt.close(fig)
print(json.dumps(out, indent=1))
