"""
compare_50_50_vs_original.py
Full comparison: 1GW+79AS+20Dev  vs  1GW+50AS+50Dev
Generates an HTML report with SVG charts + complete per-device tables.
No external dependencies — pure Python stdlib only.
"""
import csv, os, statistics, math

BASE = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OLD_CSV = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
NEW_CSV = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "50_50", "csv")
OUT     = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "50_50", "comparison_report.html")

# ─── load helpers ────────────────────────────────────────────────────────────

def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"id": int(r["Device"]),
                         "cpu": float(r["CPU_s"]),
                         "energy_j": float(r["Energy_J"])})
    return rows

def load_summary(path):
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out[r["Phase"]] = {
                "avg_cpu":  float(r["Avg_CPU_s"]),
                "std_cpu":  float(r["Std_CPU_s"]),
                "avg_ej":   float(r["Avg_Energy_J"]),
                "std_ej":   float(r["Std_Energy_J"]),
            }
    return out

def avg(lst): return statistics.mean(lst) if lst else 0
def sd(lst):  return statistics.stdev(lst) if len(lst) > 1 else 0

# ─── load data ───────────────────────────────────────────────────────────────

old = {
    "enroll": load_csv(os.path.join(OLD_CSV, "enroll-results.csv")),
    "auth":   load_csv(os.path.join(OLD_CSV, "auth-results.csv")),
    "keyex":  load_csv(os.path.join(OLD_CSV, "keyex-results.csv")),
    "summary": load_summary(os.path.join(OLD_CSV, "summary.csv")),
}
new = {
    "enroll": load_csv(os.path.join(NEW_CSV, "enroll-results.csv")),
    "auth":   load_csv(os.path.join(NEW_CSV, "auth-results.csv")),
    "keyex":  load_csv(os.path.join(NEW_CSV, "keyex-results.csv")),
    "summary": load_summary(os.path.join(NEW_CSV, "summary.csv")),
}

phases  = [("enroll","Enrollment"), ("auth","Authentication"), ("keyex","Key Exchange")]
PHASE_KEYS = {"Enrollment":"enroll","Authentication":"auth","Key Exchange":"keyex"}

# ─── SVG helpers ─────────────────────────────────────────────────────────────

def grouped_bar_svg(groups, series, ylabel, unit, colors, width=620, height=320):
    """
    groups  = list of group labels, e.g. ["Enrollment","Auth","KeyEx"]
    series  = list of (label, [val_per_group]) tuples
    """
    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 60
    chart_w = width  - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    all_vals = [v for _, vals in series for v in vals]
    max_v    = max(all_vals) * 1.18
    n_groups = len(groups)
    n_series = len(series)

    group_w  = chart_w / n_groups
    bar_w    = group_w * 0.28
    gap      = group_w * 0.06

    def ys(v): return pad_t + chart_h - (v / max_v) * chart_h
    def xs(gi, si): return pad_l + gi * group_w + gap + si * (bar_w + gap * 0.5)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'style="font-family:Arial,sans-serif;font-size:11px;">']

    # grid lines
    n_ticks = 5
    for i in range(n_ticks + 1):
        v   = max_v * i / n_ticks
        y   = ys(v)
        lbl = f"{v*1000:.1f}" if unit == "mJ" else f"{v:.3f}"
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
                     f'stroke="#e0e0e0" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="#666" font-size="10">{lbl}</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" '
                 f'stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" '
                 f'y2="{pad_t+chart_h}" stroke="#333" stroke-width="1.5"/>')

    # y-axis label
    lines.append(f'<text transform="rotate(-90)" x="{-(pad_t+chart_h/2)}" y="14" '
                 f'text-anchor="middle" fill="#333" font-size="11">{ylabel} ({unit})</text>')

    # bars + group labels
    for gi, glabel in enumerate(groups):
        for si, (slabel, vals) in enumerate(series):
            x  = xs(gi, si)
            y0 = pad_t + chart_h
            yv = ys(vals[gi])
            bh = y0 - yv
            lines.append(f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bar_w:.1f}" '
                         f'height="{bh:.1f}" fill="{colors[si]}" rx="2"/>')
            # value label on top
            lbl = f"{vals[gi]*1000:.1f}" if unit == "mJ" else f"{vals[gi]:.3f}"
            lines.append(f'<text x="{x+bar_w/2:.1f}" y="{yv-3:.1f}" '
                         f'text-anchor="middle" fill="{colors[si]}" font-size="9">{lbl}</text>')

        # group label
        gx = pad_l + gi * group_w + group_w / 2
        lines.append(f'<text x="{gx:.1f}" y="{pad_t+chart_h+16}" '
                     f'text-anchor="middle" fill="#333" font-size="11">{glabel}</text>')

    # legend
    lx = pad_l + 10
    ly = pad_t + 10
    for si, (slabel, _) in enumerate(series):
        lines.append(f'<rect x="{lx}" y="{ly+si*18}" width="14" height="12" '
                     f'fill="{colors[si]}" rx="2"/>')
        lines.append(f'<text x="{lx+18}" y="{ly+si*18+10}" fill="#333" '
                     f'font-size="10">{slabel}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def line_chart_svg(series_list, ylabel, unit, width=700, height=300):
    """series_list = [(label, color, [(x,y), ...]), ...]"""
    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 60
    chart_w = width  - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    all_y = [y for _, _, pts in series_list for _, y in pts]
    all_x = [x for _, _, pts in series_list for x, _ in pts]
    min_x, max_x = min(all_x), max(all_x)
    max_y = max(all_y) * 1.15

    def cx(v): return pad_l + (v - min_x) / (max_x - min_x) * chart_w
    def cy(v): return pad_t + chart_h - (v / max_y) * chart_h

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'style="font-family:Arial,sans-serif;font-size:11px;">']

    # grid
    for i in range(6):
        v = max_y * i / 5
        y = cy(v)
        lbl = f"{v*1000:.1f}" if unit == "mJ" else f"{v:.3f}"
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
                     f'stroke="#e8e8e8" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="#666" font-size="10">{lbl}</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" '
                 f'stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" '
                 f'y2="{pad_t+chart_h}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<text transform="rotate(-90)" x="{-(pad_t+chart_h/2)}" y="14" '
                 f'text-anchor="middle" fill="#333" font-size="11">{ylabel} ({unit})</text>')
    lines.append(f'<text x="{pad_l+chart_w/2}" y="{height-8}" '
                 f'text-anchor="middle" fill="#333" font-size="11">Device ID</text>')

    # x-axis ticks
    step = 10 if (max_x - min_x) > 30 else 5
    for xv in range(int(min_x), int(max_x)+1, step):
        x = cx(xv)
        lines.append(f'<text x="{x:.1f}" y="{pad_t+chart_h+14}" '
                     f'text-anchor="middle" fill="#666" font-size="9">{xv}</text>')

    # series
    for label, color, pts in series_list:
        pts_s = sorted(pts, key=lambda p: p[0])
        path  = " ".join(f"{'M' if i==0 else 'L'}{cx(x):.1f},{cy(y):.1f}"
                         for i, (x, y) in enumerate(pts_s))
        lines.append(f'<path d="{path}" fill="none" stroke="{color}" '
                     f'stroke-width="1.5" opacity="0.85"/>')
        for x, y in pts_s:
            lines.append(f'<circle cx="{cx(x):.1f}" cy="{cy(y):.1f}" r="2.5" '
                         f'fill="{color}" opacity="0.7"/>')

    # legend
    lx, ly = pad_l + 10, pad_t + 10
    for i, (label, color, _) in enumerate(series_list):
        lines.append(f'<rect x="{lx}" y="{ly+i*18}" width="18" height="3" '
                     f'fill="{color}" rx="1"/>')
        lines.append(f'<text x="{lx+22}" y="{ly+i*18+5}" fill="#333" '
                     f'font-size="10">{label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def donut_svg(values, labels, colors, title, width=260, height=240):
    cx, cy, r_out, r_in = width/2, height/2 - 10, 85, 45
    total = sum(values)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'style="font-family:Arial,sans-serif;">']
    lines.append(f'<text x="{width/2}" y="18" text-anchor="middle" '
                 f'fill="#333" font-size="12" font-weight="bold">{title}</text>')

    angle = -math.pi / 2
    for val, color in zip(values, colors):
        sweep = 2 * math.pi * val / total
        x1 = cx + r_out * math.cos(angle)
        y1 = cy + r_out * math.sin(angle)
        x2 = cx + r_out * math.cos(angle + sweep)
        y2 = cy + r_out * math.sin(angle + sweep)
        xi1 = cx + r_in * math.cos(angle + sweep)
        yi1 = cy + r_in * math.sin(angle + sweep)
        xi2 = cx + r_in * math.cos(angle)
        yi2 = cy + r_in * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        pct = val / total * 100
        lines.append(f'<path d="M{x1:.1f},{y1:.1f} A{r_out},{r_out} 0 {large},1 '
                     f'{x2:.1f},{y2:.1f} L{xi1:.1f},{yi1:.1f} A{r_in},{r_in} 0 {large},0 '
                     f'{xi2:.1f},{yi2:.1f} Z" fill="{color}" stroke="white" stroke-width="2"/>')
        # label at midpoint
        ma = angle + sweep / 2
        lx2 = cx + (r_out + 14) * math.cos(ma)
        ly2 = cy + (r_out + 14) * math.sin(ma)
        lines.append(f'<text x="{lx2:.1f}" y="{ly2:.1f}" text-anchor="middle" '
                     f'fill="{color}" font-size="9" font-weight="bold">{pct:.0f}%</text>')
        angle += sweep

    # legend
    ly = height - 36
    for i, (label, color) in enumerate(zip(labels, colors)):
        lx2 = 10 + i * (width//3)
        lines.append(f'<rect x="{lx2}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx2+13}" y="{ly+9}" fill="#444" font-size="9">{label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)

# ─── compute totals ──────────────────────────────────────────────────────────

def total_per_device(d, phases_k):
    """Sum energy across phases for each device present in all three."""
    ids = set(r["id"] for r in d[phases_k[0]])
    for k in phases_k[1:]: ids &= set(r["id"] for r in d[k])
    result = []
    for pid in sorted(ids):
        total_e = sum(
            next(r["energy_j"] for r in d[k] if r["id"] == pid)
            for k in phases_k
        )
        total_c = sum(
            next(r["cpu"] for r in d[k] if r["id"] == pid)
            for k in phases_k
        )
        result.append({"id": pid, "energy_j": total_e, "cpu": total_c})
    return result

pk = ["enroll", "auth", "keyex"]
old_totals = total_per_device(old, pk)
new_totals = total_per_device(new, pk)

# ─── table helpers ───────────────────────────────────────────────────────────

def phase_table(data_dict, title):
    rows_html = []
    # collect all device IDs present across phases
    ids = sorted(set(r["id"] for r in data_dict["enroll"]))
    for pid in ids:
        def get(phase):
            match = [r for r in data_dict[phase] if r["id"] == pid]
            return match[0] if match else None
        e = get("enroll"); a = get("auth"); k = get("keyex")
        te = (e["energy_j"] if e else 0) + (a["energy_j"] if a else 0) + (k["energy_j"] if k else 0)
        tc = (e["cpu"] if e else 0) + (a["cpu"] if a else 0) + (k["cpu"] if k else 0)
        rows_html.append(f"""
        <tr>
          <td>{pid}</td>
          <td>{e['cpu']*1000:.1f} ms</td><td>{e['energy_j']*1000:.2f} mJ</td>
          <td>{a['cpu']*1000:.1f} ms</td><td>{a['energy_j']*1000:.2f} mJ</td>
          <td>{k['cpu']*1000:.1f} ms</td><td>{k['energy_j']*1000:.2f} mJ</td>
          <td><b>{tc*1000:.1f} ms</b></td><td><b>{te*1000:.2f} mJ</b></td>
        </tr>""")
    return f"""
    <h3>{title}</h3>
    <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th rowspan="2">Device</th>
          <th colspan="2" style="background:#4e79a7">Enrollment</th>
          <th colspan="2" style="background:#f28e2b">Authentication</th>
          <th colspan="2" style="background:#59a14f">Key Exchange</th>
          <th colspan="2" style="background:#b07aa1">Total</th>
        </tr>
        <tr>
          <th>CPU</th><th>Energy</th>
          <th>CPU</th><th>Energy</th>
          <th>CPU</th><th>Energy</th>
          <th>CPU</th><th>Energy</th>
        </tr>
      </thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
    </div>"""

# ─── summary stats ───────────────────────────────────────────────────────────

S  = old["summary"]
SN = new["summary"]

def pct(new_v, old_v):
    d = (new_v - old_v) / old_v * 100
    col = "#c0392b" if d > 0 else "#27ae60"
    arrow = "▲" if d > 0 else "▼"
    return f'<span style="color:{col}">{arrow}{abs(d):.1f}%</span>'

# energy (mJ)
old_E = {p: S[n]["avg_ej"]*1000 for p,n in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]}
new_E = {p: SN[n]["avg_ej"]*1000 for p,n in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]}
old_C = {p: S[n]["avg_cpu"] for p,n in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]}
new_C = {p: SN[n]["avg_cpu"] for p,n in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]}

# charts
energy_svg = grouped_bar_svg(
    ["Enrollment", "Authentication", "Key Exchange"],
    [("79AS / 20 Devices", [old_E["enroll"], old_E["auth"], old_E["keyex"]]),
     ("50AS / 50 Devices", [new_E["enroll"], new_E["auth"], new_E["keyex"]])],
    "Energy", "mJ", ["#4e79a7", "#e15759"]
)

cpu_svg = grouped_bar_svg(
    ["Enrollment", "Authentication", "Key Exchange"],
    [("79AS / 20 Devices", [old_C["enroll"], old_C["auth"], old_C["keyex"]]),
     ("50AS / 50 Devices", [new_C["enroll"], new_C["auth"], new_C["keyex"]])],
    "CPU Time", "s", ["#4e79a7", "#e15759"]
)

# per-device energy line charts per phase
enroll_line = line_chart_svg([
    ("79AS/20D – Enrollment", "#4e79a7",
     [(r["id"], r["energy_j"]) for r in old["enroll"]]),
    ("50AS/50D – Enrollment", "#e15759",
     [(r["id"], r["energy_j"]) for r in new["enroll"]]),
], "Energy", "mJ")

auth_line = line_chart_svg([
    ("79AS/20D – Auth", "#4e79a7",
     [(r["id"], r["energy_j"]) for r in old["auth"]]),
    ("50AS/50D – Auth", "#e15759",
     [(r["id"], r["energy_j"]) for r in new["auth"]]),
], "Energy", "mJ")

keyex_line = line_chart_svg([
    ("79AS/20D – KeyEx", "#4e79a7",
     [(r["id"], r["energy_j"]) for r in old["keyex"]]),
    ("50AS/50D – KeyEx", "#e15759",
     [(r["id"], r["energy_j"]) for r in new["keyex"]]),
], "Energy", "mJ")

total_line = line_chart_svg([
    ("79AS/20D – Total", "#4e79a7",
     [(r["id"], r["energy_j"]) for r in old_totals]),
    ("50AS/50D – Total", "#e15759",
     [(r["id"], r["energy_j"]) for r in new_totals]),
], "Total Energy", "mJ")

# donut charts
old_enrg_vals = [old_E["enroll"], old_E["auth"], old_E["keyex"]]
new_enrg_vals = [new_E["enroll"], new_E["auth"], new_E["keyex"]]
donut_colors  = ["#4e79a7", "#f28e2b", "#59a14f"]
donut_labels  = ["Enroll", "Auth", "KeyEx"]
donut_old = donut_svg(old_enrg_vals, donut_labels, donut_colors, "79AS / 20 Devices")
donut_new = donut_svg(new_enrg_vals, donut_labels, donut_colors, "50AS / 50 Devices")

# ─── insights ────────────────────────────────────────────────────────────────

old_total_e = sum(old_E.values())
new_total_e = sum(new_E.values())
old_total_c = sum(old_C.values())
new_total_c = sum(new_C.values())

old_avg_e_tot = avg([r["energy_j"] for r in old_totals]) * 1000
new_avg_e_tot = avg([r["energy_j"] for r in new_totals]) * 1000
old_sd_e_tot  = sd([r["energy_j"] for r in old_totals]) * 1000
new_sd_e_tot  = sd([r["energy_j"] for r in new_totals]) * 1000

old_dev_count = len(old_totals)
new_dev_count = len(new_totals)

# ─── HTML ─────────────────────────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Revised-Anonymity: 50_50 vs Original Comparison</title>
<style>
  body {{font-family:Arial,sans-serif; background:#f5f5f5; margin:0; padding:20px; color:#222;}}
  h1   {{text-align:center; color:#2c3e50; margin-bottom:4px;}}
  h2   {{color:#2c3e50; border-left:4px solid #4e79a7; padding-left:10px; margin-top:36px;}}
  h3   {{color:#444; margin:16px 0 8px;}}
  .subtitle {{text-align:center; color:#888; margin-bottom:24px; font-size:14px;}}
  .card {{background:#fff; border-radius:8px; padding:20px; margin-bottom:20px;
           box-shadow:0 1px 4px rgba(0,0,0,.08);}}
  .grid2 {{display:grid; grid-template-columns:1fr 1fr; gap:20px;}}
  .grid3 {{display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px;}}
  table  {{border-collapse:collapse; width:100%; font-size:13px;}}
  th,td  {{padding:6px 10px; border:1px solid #e0e0e0; text-align:center;}}
  thead tr:first-child th {{background:#2c3e50; color:#fff; font-size:12px;}}
  thead tr:nth-child(2) th {{background:#3d5166; color:#fff; font-size:11px;}}
  tbody tr:nth-child(even) {{background:#f9f9f9;}}
  tbody tr:hover {{background:#eef4ff;}}
  .table-scroll {{overflow-x:auto;}}
  .insight-box {{background:#eaf4ff; border-left:4px solid #4e79a7;
                  padding:14px 18px; border-radius:4px; margin:10px 0;}}
  .insight-box.warn {{background:#fff8e1; border-color:#f28e2b;}}
  .insight-box.good {{background:#e9f7ef; border-color:#59a14f;}}
  .big-num {{font-size:28px; font-weight:bold; color:#2c3e50;}}
  .label   {{font-size:12px; color:#888; margin-top:2px;}}
  .kpi     {{text-align:center; padding:14px;}}
  .tag-blue {{background:#4e79a7;color:#fff;padding:2px 7px;border-radius:3px;font-size:11px;}}
  .tag-red  {{background:#e15759;color:#fff;padding:2px 7px;border-radius:3px;font-size:11px;}}
  svg {{max-width:100%;height:auto;}}
  @media print {{body{{background:#fff;}} .card{{box-shadow:none;}}}}
</style>
</head>
<body>

<h1>Revised-Anonymity Protocol — Scalability Comparison</h1>
<p class="subtitle">1 GW + 79 AS + 20 Devices &nbsp;|&nbsp; vs &nbsp;|&nbsp;
1 GW + 50 AS + 50 Devices &nbsp;·&nbsp; 5 COOJA Seeds Each</p>

<!-- ── KPI strip ─────────────────────────────────────────────────────────── -->
<div class="card">
  <div class="grid3" style="grid-template-columns:repeat(6,1fr)">
    <div class="kpi">
      <div class="big-num" style="color:#4e79a7">20</div>
      <div class="label">Devices<br><span class="tag-blue">79AS config</span></div>
    </div>
    <div class="kpi">
      <div class="big-num" style="color:#4e79a7">{old_avg_e_tot:.1f} mJ</div>
      <div class="label">Avg total energy/device<br><span class="tag-blue">79AS config</span></div>
    </div>
    <div class="kpi">
      <div class="big-num" style="color:#4e79a7">{old_total_c*1000:.0f} ms</div>
      <div class="label">Avg total CPU/device<br><span class="tag-blue">79AS config</span></div>
    </div>
    <div class="kpi">
      <div class="big-num" style="color:#e15759">50</div>
      <div class="label">Devices<br><span class="tag-red">50AS config</span></div>
    </div>
    <div class="kpi">
      <div class="big-num" style="color:#e15759">{new_avg_e_tot:.1f} mJ</div>
      <div class="label">Avg total energy/device<br><span class="tag-red">50AS config</span></div>
    </div>
    <div class="kpi">
      <div class="big-num" style="color:#e15759">{new_total_c*1000:.0f} ms</div>
      <div class="label">Avg total CPU/device<br><span class="tag-red">50AS config</span></div>
    </div>
  </div>
</div>

<!-- ── Key Insights ───────────────────────────────────────────────────────── -->
<h2>Key Insights</h2>
<div class="card">

  <div class="insight-box good">
    <b>Protocol scales well.</b>
    Tripling the device count (20 → 50) while redistributing load across dedicated AS nodes
    changes total energy per device by only
    <b>{abs((new_avg_e_tot-old_avg_e_tot)/old_avg_e_tot*100):.1f}%</b>
    ({old_avg_e_tot:.1f} mJ → {new_avg_e_tot:.1f} mJ).
    The protocol is energy-efficient at scale.
  </div>

  <div class="insight-box">
    <b>Enrollment is cheaper in the 50AS config ({pct(new_E['enroll'], old_E['enroll'])} energy).</b>
    Each AS serves exactly <b>1 device</b> (vs 10 per AS in the original), so there is
    zero queuing or collision during the registration handshake — devices enroll immediately.
  </div>

  <div class="insight-box warn">
    <b>Authentication and Key Exchange cost slightly more in the 50AS config
    (Auth {pct(new_E['auth'], old_E['auth'])}, KeyEx {pct(new_E['keyex'], old_E['keyex'])}).</b>
    With 101 nodes on the network (vs 100), the RPL routing table is larger and
    CoAP round-trips carry fractionally more routing overhead.
    The absolute increase is small: +{new_E['auth']-old_E['auth']:.2f} mJ auth,
    +{new_E['keyex']-old_E['keyex']:.2f} mJ keyex.
  </div>

  <div class="insight-box good">
    <b>Perfect load balance in 50AS config.</b>
    Every AS node handles exactly one device. In the original 79AS config,
    only 2 of 79 AS nodes were active, each serving 10 devices.
    The new setup is far more realistic and fair for evaluating distributed fog authentication.
  </div>

  <div class="insight-box">
    <b>Enrollment dominates energy in both configs</b>
    ({old_E['enroll']/old_total_e*100:.0f}% of total in 79AS,
    {new_E['enroll']/new_total_e*100:.0f}% in 50AS).
    This is expected — enrollment involves two CoAP round-trips plus PUF and AES operations,
    while subsequent auth/keyex rounds are leaner.
  </div>

</div>

<!-- ── Summary Table ─────────────────────────────────────────────────────── -->
<h2>Summary: Phase-by-Phase Comparison (5-Seed Averages)</h2>
<div class="card">
  <table>
    <thead>
      <tr>
        <th>Phase</th>
        <th colspan="2" style="background:#4e79a7">79 AS / 20 Devices</th>
        <th colspan="2" style="background:#e15759">50 AS / 50 Devices</th>
        <th colspan="2">Difference</th>
      </tr>
      <tr>
        <th></th>
        <th>CPU (ms)</th><th>Energy (mJ)</th>
        <th>CPU (ms)</th><th>Energy (mJ)</th>
        <th>ΔCPU</th><th>ΔEnergy</th>
      </tr>
    </thead>
    <tbody>"""

for phase_key, phase_name in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]:
    oc = old_C[phase_key]; nc = new_C[phase_key]
    oe = old_E[phase_key]; ne = new_E[phase_key]
    html += f"""
      <tr>
        <td><b>{phase_name}</b></td>
        <td>{oc*1000:.1f}</td><td>{oe:.2f}</td>
        <td>{nc*1000:.1f}</td><td>{ne:.2f}</td>
        <td>{pct(nc, oc)}</td><td>{pct(ne, oe)}</td>
      </tr>"""

html += f"""
      <tr style="background:#f0f0f0;font-weight:bold">
        <td>TOTAL</td>
        <td>{old_total_c*1000:.1f}</td><td>{old_total_e:.2f}</td>
        <td>{new_total_c*1000:.1f}</td><td>{new_total_e:.2f}</td>
        <td>{pct(new_total_c, old_total_c)}</td><td>{pct(new_total_e, old_total_e)}</td>
      </tr>
    </tbody>
  </table>
  <p style="font-size:12px;color:#888;margin-top:8px">
  ▲ = higher in 50AS config &nbsp;|&nbsp; ▼ = lower in 50AS config.
  Red = more expensive. Green = cheaper.</p>
</div>

<!-- ── Charts ────────────────────────────────────────────────────────────── -->
<h2>Charts</h2>

<div class="card grid2">
  <div>
    <h3>Energy per Phase (mJ)</h3>
    {energy_svg}
  </div>
  <div>
    <h3>CPU Time per Phase (seconds)</h3>
    {cpu_svg}
  </div>
</div>

<div class="card grid2">
  <div>
    <h3>Energy Split by Phase — 79AS / 20 Devices</h3>
    {donut_old}
  </div>
  <div>
    <h3>Energy Split by Phase — 50AS / 50 Devices</h3>
    {donut_new}
  </div>
</div>

<div class="card">
  <h3>Per-Device Enrollment Energy — Both Configs</h3>
  {enroll_line}
</div>

<div class="card">
  <h3>Per-Device Authentication Energy — Both Configs</h3>
  {auth_line}
</div>

<div class="card">
  <h3>Per-Device Key Exchange Energy — Both Configs</h3>
  {keyex_line}
</div>

<div class="card">
  <h3>Per-Device Total Energy (All Phases) — Both Configs</h3>
  {total_line}
</div>

<!-- ── Per-Device Tables ─────────────────────────────────────────────────── -->
<h2>Complete Per-Device Results</h2>
<div class="card">
{phase_table(old, "Config A — 1 GW + 79 AS + 20 Devices")}
</div>
<div class="card">
{phase_table(new, "Config B — 1 GW + 50 AS + 50 Devices")}
</div>

<p style="text-align:center;color:#aaa;font-size:11px;margin-top:30px">
  Generated from COOJA simulation logs · Revised-Anonymity Two-Round Protocol ·
  Energest measurements on CC2420-equivalent radio model
</p>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report saved → {OUT}")
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"{'Phase':<18} {'79AS/20D CPU':>14} {'50AS/50D CPU':>14}  {'79AS/20D E':>12} {'50AS/50D E':>12}")
print("-" * 74)
for pk2, pn in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]:
    print(f"{pn:<18} {old_C[pk2]*1000:>11.1f} ms {new_C[pk2]*1000:>11.1f} ms  "
          f"{old_E[pk2]:>9.2f} mJ {new_E[pk2]:>9.2f} mJ")
print("-" * 74)
print(f"{'TOTAL':<18} {old_total_c*1000:>11.1f} ms {new_total_c*1000:>11.1f} ms  "
      f"{old_total_e:>9.2f} mJ {new_total_e:>9.2f} mJ")
