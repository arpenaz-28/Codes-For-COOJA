import paramiko, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
REMOTE_DIR = "ANUP_Hardware_Simulation"
PASSWORD = "raspberrypi"

def scp(local_path, ip, user, fname=None):
    fname = fname or os.path.basename(local_path)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username=user, password=PASSWORD, timeout=10)
    c.exec_command(f"mkdir -p ~/{REMOTE_DIR}")
    time.sleep(0.3)
    sftp = c.open_sftp()
    sftp.put(local_path, f"/home/{user}/{REMOTE_DIR}/{fname}")
    sftp.close()
    c.close()
    print(f"  OK: {fname} -> {user}@{ip}")

print("Pushing updated scripts to Pi (Device)...")
scp(os.path.join(HERE, "hw_laaka_device.py"), "192.168.1.113", "pi")
scp(os.path.join(HERE, "..", "common.py"),    "192.168.1.113", "pi")
scp(os.path.join(HERE, "..", "config.py"),    "192.168.1.113", "pi")

print("\nPushing updated scripts to Apex (Fog)...")
scp(os.path.join(HERE, "hw_laaka_fog.py"),    "192.168.1.132", "apex")
scp(os.path.join(HERE, "..", "common.py"),    "192.168.1.132", "apex")
scp(os.path.join(HERE, "..", "config.py"),    "192.168.1.132", "apex")

print("\nAll scripts updated. Ready to run.")
