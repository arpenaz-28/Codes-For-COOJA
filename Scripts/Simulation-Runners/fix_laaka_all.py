#!/usr/bin/env python3
"""
fix_laaka_all.py
================
Re-parse ALL LAAKA simulation log files (network-variation, AS-variation,
and 10-seed comparison) with the corrected formula:

  total = enroll + AUTH    (KEYEX dropped — it is a sub-window of AUTH)

LAAKA's AUTH_ENERGY in device-node.c is measured from the start of the
auth block (reg_snap, line 435) to after data (auth_snap, line 538), so
it already covers the full round (auth-req + ack + data).  KEYEX_ENERGY
(keyex_after - keyex_before, lines 487→512) is the auth+ack sub-window
inside AUTH, so adding it double-counts those messages.

For each simulation directory, this script:
  1. Re-parses all log files.
  2. Overwrites enroll-results.csv, auth-results.csv (corrected).
  3. Sets keyex-results.csv to zero rows (keeps file for schema compat).
  4. Rebuilds summary.csv.
"""

import csv, glob, math, os, re, statistics

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

_PAT_ENROLL = re.compile(
    r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_AUTH = re.compile(
    r'AUTH_ENERGY\|(\d+)\|(?:cpu_ticks=[\d.eE+\-]+\|energy_ticks=[\d.eE+\-]+\|)?'
    r'cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')


def parse_log(path):
    """Return {node_id: (cpu_s, energy_j)} for enroll and auth (mean of rounds)."""
    text = open(path).read()
    enroll, auth_rounds = {}, {}
    for m in _PAT_ENROLL.finditer(text):
        nid = int(m.group(1))
        enroll[nid] = (float(m.group(2)), float(m.group(3)))
    for m in _PAT_AUTH.finditer(text):
        nid = int(m.group(1))
        auth_rounds.setdefault(nid, []).append((float(m.group(2)), float(m.group(3))))
    auth = {nid: (statistics.mean(r[0] for r in rounds),
                  statistics.mean(r[1] for r in rounds))
            for nid, rounds in auth_rounds.items()}
    return enroll, auth


def ci95(vals):
    n = len(vals)
    return 0.0 if n < 2 else 1.96 * statistics.stdev(vals) / math.sqrt(n)


def avg_phase(per_seed, phase_key):
    """Return per-device mean across seeds for a phase."""
    per_dev = {}
    for rec in per_seed:
        for nid, (cpu, e) in rec[phase_key].items():
            per_dev.setdefault(nid, {"cpu": [], "e": []})
            per_dev[nid]["cpu"].append(cpu)
            per_dev[nid]["e"].append(e)
    return {nid: (statistics.mean(v["cpu"]), statistics.mean(v["e"]))
            for nid, v in per_dev.items()}


def write_per_device_csv(data, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID", "CPU_Time_s", "Energy_J"])
        for nid in sorted(data):
            cpu, e = data[nid]
            w.writerow([nid, f"{cpu:.6f}", f"{e:.8f}"])


def write_zero_keyex(devices, path):
    """Write a keyex-results.csv with zeros (keyex excluded from total)."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID", "CPU_Time_s", "Energy_J"])
        for nid in sorted(devices):
            w.writerow([nid, "0.000000", "0.00000000"])


def write_summary(per_seed, out_dir, n_seeds):
    """Write summary.csv matching run_as_variation.py format exactly.

    Each entry in per_seed is a dict {nid: (cpu, energy_j)}.
    We compute per-seed means (one value per seed), then average those,
    and write n_devices = devices-per-seed (NOT total data points).
    """
    phases = {
        "Enrollment":    [rec["enroll"]  for rec in per_seed],
        "Authentication":[rec["auth"]    for rec in per_seed],
        "Key Exchange":  [rec["keyex"]   for rec in per_seed],
    }
    path = os.path.join(out_dir, "summary.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Seeds", "n_devices",
                    "Avg_CPU_s", "Std_CPU_s", "CI95_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ", "CI95_Energy_mJ"])
        for name, seed_recs in phases.items():
            # seed_recs is a list (one entry per seed) of dicts {nid: (cpu, energy_j)}
            per_seed_cpu, per_seed_e, ns = [], [], []
            for d in seed_recs:
                if not d:
                    continue
                cpus = [v[0] for v in d.values()]
                ejs  = [v[1] for v in d.values()]
                per_seed_cpu.append(statistics.mean(cpus))
                per_seed_e.append(statistics.mean(ejs) * 1000)  # J → mJ
                ns.append(len(d))
            if not per_seed_cpu:
                continue
            n_avg = int(round(statistics.mean(ns)))  # devices per seed (e.g. 20)
            ae = statistics.mean(per_seed_e)
            ac = statistics.mean(per_seed_cpu)
            se = statistics.stdev(per_seed_e)  if len(per_seed_e)  > 1 else 0.0
            sc = statistics.stdev(per_seed_cpu) if len(per_seed_cpu) > 1 else 0.0
            ce = ci95(per_seed_e)
            cc = ci95(per_seed_cpu)
            w.writerow([name, n_seeds, n_avg,
                        f"{ac:.6f}", f"{sc:.6f}", f"{cc:.6f}",
                        f"{ae:.4f}",  f"{se:.4f}",  f"{ce:.4f}"])
    return path


def process_dir(log_dir, csv_dir, label=""):
    logs = sorted(glob.glob(os.path.join(log_dir, "testlog*.txt")))
    if not logs:
        print(f"  [{label}] No logs in {log_dir}")
        return None
    per_seed = []
    for lp in logs:
        enroll, auth = parse_log(lp)
        # keyex = zero (excluded)
        keyex = {nid: (0.0, 0.0) for nid in set(enroll) | set(auth)}
        per_seed.append({"enroll": enroll, "auth": auth, "keyex": keyex})

    all_devs = set()
    for rec in per_seed:
        all_devs |= set(rec["enroll"]) | set(rec["auth"])

    avg_enroll = avg_phase(per_seed, "enroll")
    avg_auth   = avg_phase(per_seed, "auth")

    os.makedirs(csv_dir, exist_ok=True)
    write_per_device_csv(avg_enroll, os.path.join(csv_dir, "enroll-results.csv"))
    write_per_device_csv(avg_auth,   os.path.join(csv_dir, "auth-results.csv"))
    write_zero_keyex(all_devs,       os.path.join(csv_dir, "keyex-results.csv"))
    sp = write_summary(per_seed, csv_dir, len(logs))

    total_per_dev = {nid: (avg_enroll.get(nid, (0,0))[1] +
                           avg_auth.get(nid, (0,0))[1]) * 1000
                     for nid in all_devs}
    if total_per_dev:
        mn = statistics.mean(total_per_dev.values())
        print(f"  [{label}] {len(logs)} seeds, {len(all_devs)} devices, "
              f"mean total/device = {mn:.2f} mJ  → {sp}")
    return mn


def main():
    print("=" * 60)
    print("LAAKA re-parse: correcting double-counted KEYEX")
    print("=" * 60)

    # ── Network variation ─────────────────────────────────────────
    net_base = os.path.join(REPO, "LAAKA", "Simulation results", "network-variation")
    print("\n── Network variation ──")
    net_totals = {}
    for n in [30, 50, 80, 100, 120]:
        log_dir = os.path.join(net_base, f"N{n}", "logs")
        csv_dir = os.path.join(net_base, f"N{n}", "csv")
        mn = process_dir(log_dir, csv_dir, label=f"N={n}")
        if mn is not None:
            net_totals[n] = mn

    # ── AS variation ──────────────────────────────────────────────
    as_base = os.path.join(REPO, "LAAKA", "Simulation results", "as-variation")
    print("\n── AS variation ──")
    as_totals = {}
    for n_as in [2, 5, 10, 15]:
        log_dir = os.path.join(as_base, f"N{n_as}", "logs")
        csv_dir = os.path.join(as_base, f"N{n_as}", "csv")
        mn = process_dir(log_dir, csv_dir, label=f"AS={n_as}")
        if mn is not None:
            as_totals[n_as] = mn

    print("\n── Summary of corrected LAAKA means ──")
    print("Network variation (per-device mean total mJ):")
    for n, mn in sorted(net_totals.items()):
        print(f"  N={n:3d}: {mn:.2f} mJ")
    print("AS variation (per-device mean total mJ):")
    for n, mn in sorted(as_totals.items()):
        print(f"  AS={n:2d}: {mn:.2f} mJ")

    print("\nDone. Run plot_network_variation.py and plot_as_variation.py to regenerate charts.")


if __name__ == "__main__":
    main()
