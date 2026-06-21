import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
run_num = int(sys.argv[1])
with open(os.path.join(HERE, "results", f"run_{run_num:02d}.json")) as f:
    d = json.load(f)
print(json.dumps(d["summary"], indent=2))
print("\nEnrollment keys:", list(d["enrollment"].keys()))
print("Round keys:", list(d["rounds"][0].keys()) if d["rounds"] else "no rounds")
