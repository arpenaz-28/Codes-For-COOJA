import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.113", username="pi", password="raspberrypi", timeout=10)
_, out, err = c.exec_command("ls ~/ANUP_Hardware_Simulation/ 2>&1 && echo '---' && ls ~/ANUP_Hardware_Simulation/*.json 2>&1")
print(out.read().decode())
print(err.read().decode())
c.close()
