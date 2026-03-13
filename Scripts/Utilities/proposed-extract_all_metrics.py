"""
Extract enrollment, key-exchange, and authentication energy metrics
from COOJA simulation log and write to CSV files.

Expected log line formats:
  ENROLL_ENERGY|<node_id>|cpu_s=<val>|energy_j=<val>
  KEYEX_ENERGY|<node_id>|cpu_s=<val>|energy_j=<val>
  The CPU time and energy at the end of authentication 1 for client <id> are <cpu> and <energy>
"""
import re
import csv
import sys
import os

def extract_metrics(logfile):
    enroll = []   # (device_id, cpu_s, energy_j)
    keyex  = []   # (device_id, cpu_s, energy_j)
    auth   = []   # (device_id, cpu_s, energy_j)

    # Patterns
    enroll_pat = re.compile(r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)')
    keyex_pat  = re.compile(r'KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)')
    auth_pat   = re.compile(r'authentication 1 for client (\d+) are ([\d.]+) and ([\d.]+)')

    with open(logfile, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = enroll_pat.search(line)
            if m:
                enroll.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
                continue
            m = keyex_pat.search(line)
            if m:
                keyex.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
                continue
            m = auth_pat.search(line)
            if m:
                auth.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))

    return enroll, keyex, auth

def write_csv(data, filename, phase_name):
    with open(filename, 'w', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(['Device', 'CPU_s', 'Energy_J'])
        for dev, cpu, energy in sorted(data):
            w.writerow([dev, f'{cpu:.6f}', f'{energy:.6f}'])
    print(f'  [{phase_name}] {len(data)} devices -> {filename}')

def main():
    if len(sys.argv) < 2:
        logfile = os.path.join(os.path.dirname(__file__), 'COOJA-100node-testlog.txt')
    else:
        logfile = sys.argv[1]

    if not os.path.isfile(logfile):
        print(f'Error: Log file not found: {logfile}')
        sys.exit(1)

    print(f'Parsing: {logfile}')
    enroll, keyex, auth = extract_metrics(logfile)

    outdir = os.path.dirname(os.path.abspath(logfile))

    if enroll:
        write_csv(enroll, os.path.join(outdir, 'enroll-results.csv'), 'Enrollment')
    else:
        print('  [Enrollment] No ENROLL_ENERGY lines found')

    if keyex:
        write_csv(keyex, os.path.join(outdir, 'keyex-results.csv'), 'Key Exchange')
    else:
        print('  [Key Exchange] No KEYEX_ENERGY lines found')

    if auth:
        write_csv(auth, os.path.join(outdir, 'auth-results.csv'), 'Authentication')
    else:
        print('  [Authentication] No auth energy lines found')

    # Summary
    print('\n--- Summary ---')
    for name, data in [('Enrollment', enroll), ('Key Exchange', keyex), ('Authentication', auth)]:
        if data:
            cpus = [d[1] for d in data]
            ens  = [d[2] for d in data]
            print(f'  {name:15s}: n={len(data):2d}  '
                  f'Avg CPU={sum(cpus)/len(cpus):.6f}s  '
                  f'Avg Energy={sum(ens)/len(ens):.6f}J')

if __name__ == '__main__':
    main()
