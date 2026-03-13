import csv

print('=== BASE SCHEME ENROLLMENT ===')
with open('Base-Scheme/enroll-results.csv') as f:
    rows = list(csv.DictReader(f))
cpus = [float(r['CPU_Time_s']) for r in rows]
ens  = [float(r['Energy_J']) for r in rows]
print(f'  Count: {len(rows)}')
print(f'  CPU  min={min(cpus):.4f} max={max(cpus):.4f} avg={sum(cpus)/len(cpus):.4f}')
print(f'  Energy min={min(ens):.4f} max={max(ens):.4f} avg={sum(ens)/len(ens):.4f}')
for r in rows:
    did = r['Device_ID']
    print(f"    Device {did}: CPU={r['CPU_Time_s']}s  Energy={r['Energy_J']}J")

print()
print('=== EXTENDED SCHEME ENROLLMENT ===')
with open('Anonymity-Extended-Base-Scheme/enroll-results.csv') as f:
    rows = list(csv.DictReader(f))
cpus = [float(r['CPU_s']) for r in rows]
ens  = [float(r['Energy_J']) for r in rows]
print(f'  Count: {len(rows)}')
print(f'  CPU  min={min(cpus):.4f} max={max(cpus):.4f} avg={sum(cpus)/len(cpus):.4f}')
print(f'  Energy min={min(ens):.4f} max={max(ens):.4f} avg={sum(ens)/len(ens):.4f}')
for r in rows:
    did = r['Device']
    print(f"    Device {did}: CPU={r['CPU_s']}s  Energy={r['Energy_J']}J")
