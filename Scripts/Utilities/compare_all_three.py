"""
compare_all_three.py
Three-way comparison:
  Config A: 1 GW + 79 AS + 20 Devices  (original)
  Config B: 1 GW + 50 AS + 50 Devices
  Config C: 1 GW + 20 AS + 79 Devices
Generates a single HTML report with SVG charts, tables, and insights.
Pure Python stdlib — no external dependencies.
"""
import csv, os, statistics, math

BASE  = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
A_CSV = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
B_CSV = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "50_50", "csv")
C_CSV = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "20_79", "csv")
OUT   = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "20_79", "comparison_all_three.html")

CONFIGS = [
    {"key": "A", "label": "79 AS / 20 Dev", "short": "79AS·20D",
     "color": "#4e79a7", "csv": A_CSV, "gw":1,"as":79,"dev":20},
    {"key": "B", "label": "50 AS / 50 Dev", "short": "50AS·50D",
     "color": "#e15759", "csv": B_CSV, "gw":1,"as":50,"dev":50},
    {"key": "C", "label": "20 AS / 79 Dev", "short": "20AS·79D",
     "color": "#59a14f", "csv": C_CSV, "gw":1,"as":20,"dev":79},
]

# ─── loaders ─────────────────────────────────────────────────────────────────

def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        # normalise header keys — strip whitespace regardless of source format
        reader.fieldnames = [k.strip() for k in reader.fieldnames]
        for r in reader:
            rows.append({"id": int(r["Device"].strip()),
                         "cpu": float(r["CPU_s"].strip()),
                         "energy_j": float(r["Energy_J"].strip())})
    return rows

def load_summary(path):
    out = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [k.strip() for k in reader.fieldnames]
        for r in reader:
            out[r["Phase"].strip()] = {
                "avg_cpu": float(r["Avg_CPU_s"].strip()),
                "std_cpu": float(r["Std_CPU_s"].strip()),
                "avg_ej":  float(r["Avg_Energy_J"].strip()),
                "std_ej":  float(r["Std_Energy_J"].strip()),
            }
    return out

def avg(lst): return statistics.mean(lst) if lst else 0.0
def sd(lst):  return statistics.stdev(lst) if len(lst) > 1 else 0.0

# ─── load all data ───────────────────────────────────────────────────────────

for cfg in CONFIGS:
    d = cfg["csv"]
    cfg["data"] = {
        "enroll":  load_csv(os.path.join(d, "enroll-results.csv")),
        "auth":    load_csv(os.path.join(d, "auth-results.csv")),
        "keyex":   load_csv(os.path.join(d, "keyex-results.csv")),
        "summary": load_summary(os.path.join(d, "summary.csv")),
    }
    s = cfg["data"]["summary"]
    cfg["E"] = {
        "enroll": s["Enrollment"]["avg_ej"]*1000,
        "auth":   s["Authentication"]["avg_ej"]*1000,
        "keyex":  s["Key Exchange"]["avg_ej"]*1000,
    }
    cfg["C"] = {
        "enroll": s["Enrollment"]["avg_cpu"],
        "auth":   s["Authentication"]["avg_cpu"],
        "keyex":  s["Key Exchange"]["avg_cpu"],
    }
    cfg["E"]["total"] = sum(cfg["E"].values())
    cfg["C"]["total"] = sum(cfg["C"].values())

    # per-device totals
    pk = ["enroll","auth","keyex"]
    ids = set(r["id"] for r in cfg["data"]["enroll"])
    for k in pk[1:]: ids &= set(r["id"] for r in cfg["data"][k])
    totals = []
    for pid in sorted(ids):
        te = sum(next(r["energy_j"] for r in cfg["data"][k] if r["id"]==pid) for k in pk)
        tc = sum(next(r["cpu"]      for r in cfg["data"][k] if r["id"]==pid) for k in pk)
        totals.append({"id": pid, "energy_j": te, "cpu": tc})
    cfg["totals"] = totals
    cfg["avg_total_e"] = avg([r["energy_j"] for r in totals])*1000
    cfg["std_total_e"] = sd([r["energy_j"]  for r in totals])*1000

# ─── SVG helpers ─────────────────────────────────────────────────────────────

def grouped_bar_svg(groups, series, ylabel, unit, width=680, height=340):
    pad_l,pad_r,pad_t,pad_b = 72,20,35,65
    cw = width-pad_l-pad_r; ch = height-pad_t-pad_b
    all_v = [v for _,vals,_ in series for v in vals]
    max_v  = max(all_v)*1.18
    ng, ns = len(groups), len(series)
    gw  = cw/ng; bw = gw*0.22; gap = gw*0.05

    def ys(v): return pad_t+ch-(v/max_v)*ch
    def xs(gi,si): return pad_l+gi*gw+gap+si*(bw+gap*0.4)

    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'style="font-family:Arial,sans-serif;font-size:11px;">']
    for i in range(6):
        v=max_v*i/5; y=ys(v)
        lbl=f"{v:.1f}" if unit in ("mJ","ms") else f"{v:.3f}"
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#e8e8e8" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" fill="#666" font-size="10">{lbl}</text>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<text transform="rotate(-90)" x="{-(pad_t+ch/2)}" y="14" text-anchor="middle" fill="#333" font-size="11">{ylabel} ({unit})</text>')

    for gi,gl in enumerate(groups):
        for si,(slabel,vals,color) in enumerate(series):
            x=xs(gi,si); y0=pad_t+ch; yv=ys(vals[gi]); bh=y0-yv
            lines.append(f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>')
            lbl=f"{vals[gi]:.1f}"
            lines.append(f'<text x="{x+bw/2:.1f}" y="{yv-3:.1f}" text-anchor="middle" fill="{color}" font-size="8">{lbl}</text>')
        gx=pad_l+gi*gw+gw/2
        lines.append(f'<text x="{gx:.1f}" y="{pad_t+ch+16}" text-anchor="middle" fill="#333" font-size="11">{gl}</text>')

    lx,ly=pad_l+10,pad_t+8
    for si,(sl,_,color) in enumerate(series):
        lines.append(f'<rect x="{lx+si*130}" y="{ly}" width="12" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+si*130+15}" y="{ly+9}" fill="#333" font-size="10">{sl}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def line_chart_svg(series_list, ylabel, unit, width=720, height=300):
    pad_l,pad_r,pad_t,pad_b=72,20,30,55
    cw=width-pad_l-pad_r; ch=height-pad_t-pad_b
    all_y=[y for _,_,pts in series_list for _,y in pts]
    all_x=[x for _,_,pts in series_list for x,_ in pts]
    mx,mnx,mx_y=max(all_x),min(all_x),max(all_y)*1.15
    def cx(v): return pad_l+(v-mnx)/(mx-mnx)*cw if mx!=mnx else pad_l+cw/2
    def cy(v): return pad_t+ch-(v/mx_y)*ch

    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'style="font-family:Arial,sans-serif;font-size:11px;">']
    for i in range(6):
        v=mx_y*i/5; y=cy(v)
        lbl=f"{v*1000:.1f}" if unit=="mJ" else f"{v:.3f}"
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#e8e8e8" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" fill="#666" font-size="10">{lbl}</text>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<text transform="rotate(-90)" x="{-(pad_t+ch/2)}" y="14" text-anchor="middle" fill="#333" font-size="11">{ylabel} ({unit})</text>')
    lines.append(f'<text x="{pad_l+cw/2}" y="{height-8}" text-anchor="middle" fill="#333" font-size="11">Device ID</text>')
    step=10 if (mx-mnx)>40 else 5
    for xv in range(int(mnx),int(mx)+1,step):
        lines.append(f'<text x="{cx(xv):.1f}" y="{pad_t+ch+13}" text-anchor="middle" fill="#888" font-size="9">{xv}</text>')
    for label,color,pts in series_list:
        spts=sorted(pts,key=lambda p:p[0])
        path=" ".join(f"{'M' if i==0 else 'L'}{cx(x):.1f},{cy(y):.1f}" for i,(x,y) in enumerate(spts))
        lines.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" opacity="0.85"/>')
        for x,y in spts:
            lines.append(f'<circle cx="{cx(x):.1f}" cy="{cy(y):.1f}" r="2.2" fill="{color}" opacity="0.7"/>')
    lx,ly=pad_l+10,pad_t+8
    for i,(label,color,_) in enumerate(series_list):
        lines.append(f'<line x1="{lx+i*160}" y1="{ly+5}" x2="{lx+i*160+18}" y2="{ly+5}" stroke="{color}" stroke-width="2.5"/>')
        lines.append(f'<text x="{lx+i*160+22}" y="{ly+9}" fill="#333" font-size="10">{label}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def stacked_bar_svg(configs, width=500, height=320):
    """Stacked bar showing Enroll+Auth+KeyEx per config."""
    pad_l,pad_r,pad_t,pad_b=72,30,35,55
    cw=width-pad_l-pad_r; ch=height-pad_t-pad_b
    colors=["#4e79a7","#f28e2b","#59a14f"]
    labels=["Enrollment","Authentication","Key Exchange"]
    max_v=max(cfg["E"]["total"] for cfg in configs)*1.12
    bw=cw/(len(configs)*1.6); gap=(cw-bw*len(configs))/(len(configs)+1)

    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'style="font-family:Arial,sans-serif;font-size:11px;">']
    for i in range(6):
        v=max_v*i/5; y=pad_t+ch-(v/max_v)*ch
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#e8e8e8" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" fill="#666" font-size="10">{v:.1f}</text>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#333" stroke-width="1.5"/>')
    lines.append(f'<text transform="rotate(-90)" x="{-(pad_t+ch/2)}" y="14" text-anchor="middle" fill="#333" font-size="11">Total Energy (mJ)</text>')

    for ci,cfg in enumerate(configs):
        x=pad_l+gap+ci*(bw+gap)
        segments=[cfg["E"]["enroll"],cfg["E"]["auth"],cfg["E"]["keyex"]]
        base=pad_t+ch
        for seg,color in zip(segments,colors):
            h=(seg/max_v)*ch
            base-=h
            lines.append(f'<rect x="{x:.1f}" y="{base:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{color}" stroke="white" stroke-width="0.5"/>')
        total=sum(segments)
        lines.append(f'<text x="{x+bw/2:.1f}" y="{pad_t+ch-(total/max_v)*ch-5:.1f}" text-anchor="middle" fill="#222" font-size="10" font-weight="bold">{total:.1f}</text>')
        lines.append(f'<text x="{x+bw/2:.1f}" y="{pad_t+ch+14}" text-anchor="middle" fill="#333" font-size="10">{cfg["short"]}</text>')

    lx,ly=pad_l+8,pad_t+8
    for i,(label,color) in enumerate(zip(labels,colors)):
        lines.append(f'<rect x="{lx}" y="{ly+i*16}" width="11" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="{ly+i*16+9}" fill="#444" font-size="9">{label}</text>')
    lines.append('</svg>')
    return "\n".join(lines)

# ─── build chart data ─────────────────────────────────────────────────────────

A,B,C = CONFIGS[0],CONFIGS[1],CONFIGS[2]

energy_svg = grouped_bar_svg(
    ["Enrollment","Authentication","Key Exchange"],
    [(cfg["label"],[cfg["E"]["enroll"],cfg["E"]["auth"],cfg["E"]["keyex"]],cfg["color"])
     for cfg in CONFIGS],
    "Energy","mJ")

cpu_svg = grouped_bar_svg(
    ["Enrollment","Authentication","Key Exchange"],
    [(cfg["label"],[cfg["C"]["enroll"]*1000,cfg["C"]["auth"]*1000,cfg["C"]["keyex"]*1000],cfg["color"])
     for cfg in CONFIGS],
    "CPU Time","ms")

stacked_svg = stacked_bar_svg(CONFIGS)

# per-phase line charts (all three configs)
def line_series(cfg, phase):
    return (cfg["label"], cfg["color"],
            [(r["id"],r["energy_j"]) for r in cfg["data"][phase]])

enroll_line = line_chart_svg([line_series(c,"enroll") for c in CONFIGS],"Energy","mJ")
auth_line   = line_chart_svg([line_series(c,"auth")   for c in CONFIGS],"Energy","mJ")
keyex_line  = line_chart_svg([line_series(c,"keyex")  for c in CONFIGS],"Energy","mJ")
total_line  = line_chart_svg(
    [(cfg["label"],cfg["color"],[(r["id"],r["energy_j"]) for r in cfg["totals"]])
     for cfg in CONFIGS], "Total Energy","mJ")

# ─── per-device table ─────────────────────────────────────────────────────────

def phase_table(cfg):
    data = cfg["data"]
    ids  = sorted(set(r["id"] for r in data["enroll"]))
    rows_html = []
    for pid in ids:
        def get(phase):
            m=[r for r in data[phase] if r["id"]==pid]
            return m[0] if m else None
        e=get("enroll"); a=get("auth"); k=get("keyex")
        te=((e["energy_j"] if e else 0)+(a["energy_j"] if a else 0)+(k["energy_j"] if k else 0))
        tc=((e["cpu"] if e else 0)+(a["cpu"] if a else 0)+(k["cpu"] if k else 0))
        rows_html.append(f"""<tr>
          <td>{pid}</td>
          <td>{e['cpu']*1000:.1f}</td><td>{e['energy_j']*1000:.2f}</td>
          <td>{a['cpu']*1000:.1f}</td><td>{a['energy_j']*1000:.2f}</td>
          <td>{k['cpu']*1000:.1f}</td><td>{k['energy_j']*1000:.2f}</td>
          <td><b>{tc*1000:.1f}</b></td><td><b>{te*1000:.2f}</b></td>
        </tr>""")
    label = f"Config — 1 GW + {cfg['as']} AS + {cfg['dev']} Devices"
    return f"""<h3 style="color:{cfg['color']}">{label}</h3>
    <div class="tscroll"><table>
      <thead><tr>
        <th rowspan="2">Device</th>
        <th colspan="2" style="background:#4e79a7">Enrollment</th>
        <th colspan="2" style="background:#f28e2b">Auth</th>
        <th colspan="2" style="background:#59a14f">KeyEx</th>
        <th colspan="2" style="background:#b07aa1">Total</th>
      </tr><tr>
        <th>CPU(ms)</th><th>E(mJ)</th>
        <th>CPU(ms)</th><th>E(mJ)</th>
        <th>CPU(ms)</th><th>E(mJ)</th>
        <th>CPU(ms)</th><th>E(mJ)</th>
      </tr></thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table></div>"""

# ─── delta helper ─────────────────────────────────────────────────────────────

def delta(new_v, ref_v):
    d=(new_v-ref_v)/ref_v*100
    col="#c0392b" if d>0 else "#27ae60"
    arrow="▲" if d>0 else "▼"
    return f'<span style="color:{col}">{arrow}{abs(d):.1f}%</span>'

# ─── HTML ─────────────────────────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>Revised-Anonymity: Three-Config Comparison</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;color:#222}}
h1{{text-align:center;color:#2c3e50;margin-bottom:4px}}
h2{{color:#2c3e50;border-left:5px solid #4e79a7;padding-left:10px;margin-top:36px}}
h3{{color:#444;margin:14px 0 6px}}
.sub{{text-align:center;color:#888;font-size:13px;margin-bottom:22px}}
.card{{background:#fff;border-radius:8px;padding:20px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
.kpi{{text-align:center;padding:14px}}
.big{{font-size:26px;font-weight:bold}}
.lbl{{font-size:11px;color:#888;margin-top:3px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{padding:5px 9px;border:1px solid #e0e0e0;text-align:center}}
thead tr:first-child th{{background:#2c3e50;color:#fff;font-size:11px}}
thead tr:nth-child(2) th{{background:#3d5166;color:#fff;font-size:10px}}
tbody tr:nth-child(even){{background:#f9f9f9}}
tbody tr:hover{{background:#eef4ff}}
.tscroll{{overflow-x:auto}}
.ins{{padding:13px 16px;border-radius:4px;margin:9px 0;border-left:4px solid}}
.ins-b{{background:#eaf4ff;border-color:#4e79a7}}
.ins-g{{background:#e9f7ef;border-color:#59a14f}}
.ins-y{{background:#fff8e1;border-color:#f28e2b}}
.ins-r{{background:#fdecea;border-color:#e15759}}
svg{{max-width:100%;height:auto}}
</style></head><body>

<h1>Revised-Anonymity Protocol — Three-Configuration Scalability Study</h1>
<p class="sub">
  <span style="color:{A['color']}">■</span> 1 GW + 79 AS + 20 Devices &nbsp;|&nbsp;
  <span style="color:{B['color']}">■</span> 1 GW + 50 AS + 50 Devices &nbsp;|&nbsp;
  <span style="color:{C['color']}">■</span> 1 GW + 20 AS + 79 Devices &nbsp;·&nbsp; 5 COOJA Seeds Each
</p>

<!-- KPI strip -->
<div class="card">
  <div style="display:grid;grid-template-columns:repeat(9,1fr);gap:4px">"""

for cfg in CONFIGS:
    html += f"""
    <div class="kpi"><div class="big" style="color:{cfg['color']}">{cfg['as']}</div><div class="lbl">AS nodes</div></div>
    <div class="kpi"><div class="big" style="color:{cfg['color']}">{cfg['dev']}</div><div class="lbl">Devices</div></div>
    <div class="kpi"><div class="big" style="color:{cfg['color']}">{cfg['avg_total_e']:.1f}<span style="font-size:14px">mJ</span></div><div class="lbl">Avg total energy/device</div></div>"""

html += """
  </div>
</div>

<!-- Insights -->
<h2>Key Insights</h2>
<div class="card">"""

# compute insights
e_ref = A["E"]["total"]; c_ref = A["C"]["total"]
b_e = B["E"]["total"]; c_e = C["E"]["total"]
b_c = B["C"]["total"]; c_c = C["C"]["total"]

html += f"""
  <div class="ins ins-g">
    <b>The protocol is remarkably stable across all three configurations.</b>
    Total energy per device:
    <b style="color:{A['color']}">{A['avg_total_e']:.1f} mJ</b> (79AS·20D) →
    <b style="color:{B['color']}">{B['avg_total_e']:.1f} mJ</b> (50AS·50D) →
    <b style="color:{C['color']}">{C['avg_total_e']:.1f} mJ</b> (20AS·79D).
    Despite varying the device count by 4× (20→79) and the AS count by 4× (79→20),
    total energy shifts by only <b>{abs(C['avg_total_e']-A['avg_total_e']):.2f} mJ
    ({abs((C['avg_total_e']-A['avg_total_e'])/A['avg_total_e']*100):.1f}%)</b>.
  </div>

  <div class="ins ins-b">
    <b>Enrollment cost follows AS-to-device ratio.</b>
    With 79 AS for 20 devices (ratio 3.95 AS/device), enrollment is
    <b>{A['E']['enroll']:.1f} mJ</b>. At 1:1 ratio (50AS·50D) it drops to
    <b>{B['E']['enroll']:.1f} mJ</b>. At 0.25:1 (20AS·79D, ~4 devices per AS)
    it rises to <b>{C['E']['enroll']:.1f} mJ</b> — more queuing
    and retransmissions when each AS is busier.
  </div>

  <div class="ins ins-y">
    <b>Authentication and Key Exchange costs rise as AS nodes decrease.</b>
    Fewer AS nodes means each one handles more devices concurrently, increasing
    CoAP wait times. Auth energy: {A['E']['auth']:.1f} → {B['E']['auth']:.1f} → {C['E']['auth']:.1f} mJ.
    KeyEx energy: {A['E']['keyex']:.1f} → {B['E']['keyex']:.1f} → {C['E']['keyex']:.1f} mJ.
    The 20AS config pays the highest per-round cost due to contention.
  </div>

  <div class="ins ins-g">
    <b>Sweet spot: 50 AS / 50 Devices gives the best overall balance.</b>
    It has the lowest enrollment cost ({B['E']['enroll']:.1f} mJ) and moderate
    auth/keyex overhead — because 1 device per AS eliminates enrollment
    queuing while keeping the RPL network manageable.
  </div>

  <div class="ins ins-b">
    <b>Load distribution summary:</b>
    79AS·20D → 0.25 devices/AS (most AS nodes idle) |
    50AS·50D → 1.0 device/AS (perfectly balanced) |
    20AS·79D → ~4 devices/AS (highest contention).
    The protocol handles all three cases gracefully, confirming good scalability.
  </div>
</div>

<!-- Summary table -->
<h2>Phase-by-Phase Summary (5-Seed Averages)</h2>
<div class="card">
<table>
  <thead>
    <tr>
      <th rowspan="2">Phase</th>
      <th colspan="2" style="background:{A['color']}">79 AS / 20 Devices</th>
      <th colspan="2" style="background:{B['color']}">50 AS / 50 Devices</th>
      <th colspan="2" style="background:{C['color']}">20 AS / 79 Devices</th>
      <th colspan="2">B vs A</th>
      <th colspan="2">C vs A</th>
    </tr>
    <tr>
      <th>CPU (ms)</th><th>Energy (mJ)</th>
      <th>CPU (ms)</th><th>Energy (mJ)</th>
      <th>CPU (ms)</th><th>Energy (mJ)</th>
      <th>ΔCPU</th><th>ΔE</th>
      <th>ΔCPU</th><th>ΔE</th>
    </tr>
  </thead>
  <tbody>"""

for pk, pn in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]:
    ac,ae=A["C"][pk]*1000,A["E"][pk]
    bc,be=B["C"][pk]*1000,B["E"][pk]
    cc,ce=C["C"][pk]*1000,C["E"][pk]
    html+=f"""<tr>
      <td><b>{pn}</b></td>
      <td>{ac:.1f}</td><td>{ae:.2f}</td>
      <td>{bc:.1f}</td><td>{be:.2f}</td>
      <td>{cc:.1f}</td><td>{ce:.2f}</td>
      <td>{delta(bc,ac)}</td><td>{delta(be,ae)}</td>
      <td>{delta(cc,ac)}</td><td>{delta(ce,ae)}</td>
    </tr>"""

html+=f"""
    <tr style="background:#f0f0f0;font-weight:bold">
      <td>TOTAL</td>
      <td>{A['C']['total']*1000:.1f}</td><td>{A['E']['total']:.2f}</td>
      <td>{B['C']['total']*1000:.1f}</td><td>{B['E']['total']:.2f}</td>
      <td>{C['C']['total']*1000:.1f}</td><td>{C['E']['total']:.2f}</td>
      <td>{delta(B['C']['total'],A['C']['total'])}</td><td>{delta(B['E']['total'],A['E']['total'])}</td>
      <td>{delta(C['C']['total'],A['C']['total'])}</td><td>{delta(C['E']['total'],A['E']['total'])}</td>
    </tr>
  </tbody>
</table>
<p style="font-size:11px;color:#888;margin-top:6px">▲ higher than A &nbsp;▼ lower than A. Red=costlier, Green=cheaper.</p>
</div>

<!-- Load distribution table -->
<h2>Network Load Distribution</h2>
<div class="card">
<table>
  <thead><tr>
    <th>Config</th><th>GW</th><th>AS Nodes</th><th>Devices</th>
    <th>Total Nodes</th><th>Devices per AS</th><th>AS utilisation</th>
  </tr></thead>
  <tbody>
    <tr><td><b style="color:{A['color']}">79 AS / 20 Dev</b></td>
        <td>1</td><td>79</td><td>20</td><td>100</td>
        <td>~0.25</td><td>Only 2 of 79 AS active (original design)</td></tr>
    <tr><td><b style="color:{B['color']}">50 AS / 50 Dev</b></td>
        <td>1</td><td>50</td><td>50</td><td>101</td>
        <td>1.0 (exactly)</td><td>All 50 AS active — perfectly balanced</td></tr>
    <tr><td><b style="color:{C['color']}">20 AS / 79 Dev</b></td>
        <td>1</td><td>20</td><td>79</td><td>100</td>
        <td>~3.95 (19×4 + 1×3)</td><td>All 20 AS active — highest load</td></tr>
  </tbody>
</table>
</div>

<!-- Charts -->
<h2>Charts</h2>
<div class="card grid2">
  <div><h3>Energy per Phase (mJ) — All Configs</h3>{energy_svg}</div>
  <div><h3>CPU Time per Phase (ms) — All Configs</h3>{cpu_svg}</div>
</div>

<div class="card grid2">
  <div><h3>Total Energy per Device — Stacked by Phase</h3>{stacked_svg}</div>
  <div style="display:flex;flex-direction:column;justify-content:center;padding:20px">
    <h3>Quick Read</h3>
    <ul style="line-height:2;font-size:13px">
      <li><b>Enrollment</b> dominates energy (~{A['E']['enroll']/A['E']['total']*100:.0f}–{C['E']['enroll']/C['E']['total']*100:.0f}% of total) across all configs</li>
      <li><b>50AS·50D</b> has lowest total: <b>{B['E']['total']:.1f} mJ</b></li>
      <li><b>20AS·79D</b> has highest total: <b>{C['E']['total']:.1f} mJ</b></li>
      <li>Range across all configs: <b>{max(cfg['E']['total'] for cfg in CONFIGS)-min(cfg['E']['total'] for cfg in CONFIGS):.2f} mJ</b> — very tight</li>
    </ul>
  </div>
</div>

<div class="card"><h3>Per-Device Enrollment Energy — All Configs</h3>{enroll_line}</div>
<div class="card"><h3>Per-Device Authentication Energy — All Configs</h3>{auth_line}</div>
<div class="card"><h3>Per-Device Key Exchange Energy — All Configs</h3>{keyex_line}</div>
<div class="card"><h3>Per-Device Total Energy (All Phases) — All Configs</h3>{total_line}</div>

<!-- Per-device tables -->
<h2>Complete Per-Device Results</h2>"""

for cfg in CONFIGS:
    html += f'<div class="card">{phase_table(cfg)}</div>'

html += f"""
<p style="text-align:center;color:#aaa;font-size:11px;margin-top:28px">
  Revised-Anonymity Two-Round Protocol · COOJA simulation ·
  Energest on CC2420-equivalent radio model · 5 seeds each config
</p>
</body></html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Report saved → {OUT}")
print()
print("=" * 72)
print(f"{'Config':<18} {'Enroll':>10} {'Auth':>10} {'KeyEx':>10} {'TOTAL':>10}  (mJ avg/device)")
print("-" * 62)
for cfg in CONFIGS:
    print(f"{cfg['label']:<18} {cfg['E']['enroll']:>10.2f} {cfg['E']['auth']:>10.2f} "
          f"{cfg['E']['keyex']:>10.2f} {cfg['E']['total']:>10.2f}")
