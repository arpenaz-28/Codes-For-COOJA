import paramiko, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
run_num = int(sys.argv[1])
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
out = os.path.join(HERE, "results", f"run_{run_num:02d}.json")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.132", username="apex", password="raspberrypi", timeout=10)
sftp = c.open_sftp()
sftp.get("/home/apex/ANUP_Hardware_Simulation/zhou_hw_run.json", out)
sftp.close()
c.close()

with open(out) as f:
    d = json.load(f)
s = d["summary"]
enr = d["enrollment"]
print(f"Run {run_num} collected -> results/run_{run_num:02d}.json")
print(f"  Enrollment   : {enr['energy_j']:.4f} J  {enr['wall_s']:.4f} s")
print(f"  Avg Auth/rnd : {s['avg_auth_energy_j']:.4f} J  {s['avg_auth_time_s']:.4f} s")
