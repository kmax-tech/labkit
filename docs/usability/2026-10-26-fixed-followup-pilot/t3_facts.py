"""Facts for the fixed-followup pilot: the closed-form identity on t3's train data."""
import csv, statistics, sys
path = sys.argv[1]
rows = list(csv.DictReader(open(path, encoding="utf-8")))
k = [float(r["K_VRH"]) for r in rows]
g = [float(r["G_VRH"]) for r in rows]
nu = [float(r["poisson_ratio"]) for r in rows]
pred = [2 * gi * (1 + ni) / (3 * (1 - 2 * ni)) for gi, ni in zip(g, nu)]
mean = statistics.fmean(k)
ss_res = sum((a - b) ** 2 for a, b in zip(k, pred))
ss_tot = sum((a - mean) ** 2 for a in k)
print("n", len(rows), "r2_identity", 1 - ss_res / ss_tot)
# linear fit of K on G alone, as a scale for what G alone carries
mg = statistics.fmean(g)
beta = sum((a - mg) * (b - mean) for a, b in zip(g, k)) / sum((a - mg) ** 2 for a in g)
pl = [mean + beta * (a - mg) for a in g]
print("r2_linear_G_only", 1 - sum((a - b) ** 2 for a, b in zip(k, pl)) / ss_tot)
print("columns", list(rows[0].keys()))
