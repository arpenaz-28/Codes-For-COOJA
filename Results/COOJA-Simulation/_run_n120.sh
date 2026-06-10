#!/bin/bash
# Sequential N=120 runs (shared myproject + COOJA.testlog → must be serial).
set -e
cd /home/apex/contiki-ng/examples/Codes-For-COOJA

echo "===== [1/2] DAuth N=120 (10 seeds) ====="
python3 - <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location("ds","/home/apex/contiki-ng/examples/Codes-For-COOJA/Scripts/Simulation-Runners/run_dauth_sweep.py")
ds=importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
seeds=ds.SEEDS[:10]
logdir=ds.os.path.join(ds.OUT_SWEEP,"network-variation","N120","logs")
per=ds.run_config("net-var N=120", 2, 95, 24, 97, seeds, logdir, 1800000)
csv_dir=ds.os.path.join(ds.OUT_SWEEP,"network-variation","N120","csv")
ds.write_summary(per, csv_dir, len(per))
ds.write_seed_results(per, csv_dir, set(range(97,121)))
print("DAuth N=120 done, seeds=",len(per))
PY

echo "===== [2/2] Proposed/LAAKA/Zhou N=120 (10 seeds each) ====="
python3 Scripts/Simulation-Runners/run_network_variation.py --scheme RA LAAKA Zhou --size 120 --seeds 10

echo "===== ALL N=120 RUNS DONE ====="
