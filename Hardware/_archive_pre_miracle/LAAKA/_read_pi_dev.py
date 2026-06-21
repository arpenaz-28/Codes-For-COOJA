import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.113", username="pi", password="raspberrypi", timeout=10)
_, out, _ = c.exec_command("tail -30 /home/pi/ANUP_Hardware_Simulation/hw_laaka_device.py")
print(out.read().decode())
c.close()
