import csv, json, sys
from openpyxl import Workbook
from openpyxl.styles import Font
SRC="NASA POWER monthly point API (MERRA-2 based), -33.45,-70.67; file POWER_punto_ilustrativo_Chile_1981_2025; analysis run 2026-11-14"
res=json.load(open("results/results.json"))["results"]
wb=Workbook(); ws=wb.active; ws.title="Monthly data"
ws.append(["year","month","days","PRECTOTCORR mm/day","precip mm/month (derived)","T2M C","source","date"])
for r in csv.DictReader(open(sys.argv[1])):
    if 1<=int(r["month"])<=12: ws.append([int(r["year"]),int(r["month"]),int(r["days_in_month"]),float(r["PRECTOTCORR_mm_per_day"]),float(r["derived_precipitation_mm_per_month"]),float(r["T2M_C"]),SRC,"2026-11-14"])
w2=wb.create_sheet("Trend results")
w2.append(["variable","period","n","Mann-Kendall z","p","Sen slope per decade","CI95 low","CI95 high","OLS per decade","OLS p","% of mean per decade","verdict","source"])
for v in ("precip","temp"):
    for k,r in res[v].items(): w2.append([v,k,r["n"],r["z"],r["p"],r["sen_per_decade"],r["ci_per_decade"][0],r["ci_per_decade"][1],r["ols_per_decade"],r["ols_p"],r["rel_change_pct_per_decade"],r["verdict"],SRC])
w3=wb.create_sheet("Period comparison")
for k,v in res["period_compare_precip"].items(): w3.append([k,v])
w3.append(["source",SRC])
w4=wb.create_sheet("Limits")
for t in ["Single MERRA-2/POWER grid point, not station data and not independent validation.","Annual totals use 45 years; monthly anomaly MK ignores autocorrelation (indicative only).","Significant trend shows change, not cause.","Verdict rule: p<0.05 strong; 0.05-0.15 weak; else not proven."]: w4.append([t])
for s in wb: 
    for c in s[1]: c.font=Font(bold=True)
wb.save("Case_File_Earth_resultados.xlsx")
