import re, statistics

log = open('/mnt/schemes/Zhou-Scheme/COOJA-fixed.testlog').read()

user_auth = {}
for m in re.finditer(r'AUTH_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)', log):
    nid, cpu, ej = int(m.group(1)), float(m.group(2)), float(m.group(3))
    if 81 <= nid <= 100:
        user_auth.setdefault(nid, []).append((cpu, ej))

user_enroll = {}
for m in re.finditer(r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)', log):
    nid, cpu, ej = int(m.group(1)), float(m.group(2)), float(m.group(3))
    if 81 <= nid <= 100:
        user_enroll[nid] = (cpu, ej)

gw_auth = {}
for m in re.finditer(r'AUTH_ENERGY_GW\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)', log):
    nid, cpu, ej = int(m.group(1)), float(m.group(2)), float(m.group(3))
    gw_auth.setdefault(nid, []).append((cpu, ej))

print("=== PER-USER AUTH ENERGY (avg over repeated rounds) ===")
print("{:<8} {:<8} {:<14} {:<16} {}".format("Device","Rounds","Avg CPU(s)","Avg Energy(J)","Enroll(J)"))
all_cpu, all_ej = [], []
for nid in sorted(user_auth):
    rounds = user_auth[nid]
    avg_cpu = statistics.mean(r[0] for r in rounds)
    avg_ej  = statistics.mean(r[1] for r in rounds)
    enroll_ej = user_enroll.get(nid, (0,0))[1]
    all_cpu.append(avg_cpu)
    all_ej.append(avg_ej)
    print("{:<8} {:<8} {:<14.6f} {:<16.6f} {:.6f}".format(nid, len(rounds), avg_cpu, avg_ej, enroll_ej))

print()
print("SUMMARY: {} devices authenticated".format(len(user_auth)))
print("  Avg Auth CPU time : {:.3f} ms".format(statistics.mean(all_cpu)*1000))
print("  Avg Auth Energy   : {:.4f} mJ".format(statistics.mean(all_ej)*1000))
print("  Min Auth Energy   : {:.4f} mJ".format(min(all_ej)*1000))
print("  Max Auth Energy   : {:.4f} mJ".format(max(all_ej)*1000))

print()
print("=== GW SERVER AUTH ENERGY (per-auth differential) ===")
for gw_id in sorted(gw_auth):
    rounds = gw_auth[gw_id]
    avg_cpu = statistics.mean(r[0] for r in rounds)
    avg_ej  = statistics.mean(r[1] for r in rounds)
    print("  GW-S {}: {} events | Avg CPU {:.3f} ms | Avg Energy {:.4f} mJ".format(
          gw_id, len(rounds), avg_cpu*1000, avg_ej*1000))

# Save CSV
import csv
out = "/mnt/schemes/Zhou-Scheme/zhou-auth-results.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Device_ID","Auth_Rounds","Avg_CPU_s","Avg_Energy_J","Enroll_Energy_J"])
    for nid in sorted(user_auth):
        rounds = user_auth[nid]
        avg_cpu = statistics.mean(r[0] for r in rounds)
        avg_ej  = statistics.mean(r[1] for r in rounds)
        enroll_ej = user_enroll.get(nid, (0,0))[1]
        w.writerow([nid, len(rounds), round(avg_cpu,6), round(avg_ej,6), round(enroll_ej,6)])
print()
print("CSV saved to:", out)
