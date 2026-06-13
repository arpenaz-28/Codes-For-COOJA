import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.113", username="pi", password="raspberrypi", timeout=10)
_, out, _ = c.exec_command("find /home/pi -name '*laaka*' -o -name '*hw_run*' 2>/dev/null")
print("Files found:")
print(out.read().decode())
c.close()
