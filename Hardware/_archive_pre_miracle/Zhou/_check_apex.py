import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.132", username="apex", password="raspberrypi", timeout=10)

_, out, _ = c.exec_command("ls ~/ANUP_Hardware_Simulation/")
print("Apex files:", out.read().decode())

_, out, _ = c.exec_command("tail -25 /home/apex/ANUP_Hardware_Simulation/hw_zhou_user.py")
print("Last 25 lines of hw_zhou_user.py on Apex:")
print(out.read().decode())
c.close()
