import re
import matplotlib.pyplot as plt
import numpy as np

log_file_path = "1MultiAuth.txt"

auth_data = {}

with open(log_file_path, "r") as f:
    for line in f:
        # Client log
        client_match = re.search(r"ID:(\d+).*for client (\d+) are (\d+\.\d+) and (\d+\.\d+)", line)
        if client_match:
            client_id = int(client_match.group(2))
            cpu = float(client_match.group(3))
            energy = float(client_match.group(4))
            auth_data.setdefault(client_id, {})['client'] = {'cpu': cpu, 'energy': energy}
            continue

        # Server log
        server_match = re.search(r"ID:(\d+).*for client (\d+) by server (\d+) is (\d+\.\d+) and (\d+\.\d+)", line)
        if server_match:
            client_id = int(server_match.group(2))
            cpu = float(server_match.group(4))
            energy = float(server_match.group(5))
            auth_data.setdefault(client_id, {})['server'] = {'cpu': cpu, 'energy': energy}
            continue

        # Gateway log
        gateway_match = re.search(r"ID:(\d+).*for client (\d+) by gateway (\d+) are (\d+\.\d+) and (\d+\.\d+)", line)
        if gateway_match:
            client_id = int(gateway_match.group(2))
            cpu = float(gateway_match.group(4))
            energy = float(gateway_match.group(5))
            auth_data.setdefault(client_id, {})['gateway'] = {'cpu': cpu, 'energy': energy}
            continue

# Separate role-wise data
client_energy_vals, client_cpu_vals = [], []
server_energy_vals, server_cpu_vals = [], []
gateway_energy_vals, gateway_cpu_vals = [], []

for client_id, roles in auth_data.items():
    if 'client' in roles:
        client_energy_vals.append(roles['client']['energy'])
        client_cpu_vals.append(roles['client']['cpu'])
    if 'server' in roles:
        server_energy_vals.append(roles['server']['energy'])
        server_cpu_vals.append(roles['server']['cpu'])
    if 'gateway' in roles:
        gateway_energy_vals.append(roles['gateway']['energy'])
        gateway_cpu_vals.append(roles['gateway']['cpu'])

# Compute averages
def avg_std(values):
    return (np.mean(values), np.std(values)) if values else (0, 0)

avg_client_energy, std_client_energy = avg_std(client_energy_vals)
avg_client_cpu, std_client_cpu = avg_std(client_cpu_vals)

avg_server_energy, std_server_energy = avg_std(server_energy_vals)
avg_server_cpu, std_server_cpu = avg_std(server_cpu_vals)

avg_gateway_energy, std_gateway_energy = avg_std(gateway_energy_vals)
avg_gateway_cpu, std_gateway_cpu = avg_std(gateway_cpu_vals)

print(f"\nClient  → Avg CPU: {avg_client_cpu:.4f} ± {std_client_cpu:.4f}, "
      f"Avg Energy: {avg_client_energy:.4f} ± {std_client_energy:.4f}")
print(f"Server  → Avg CPU: {avg_server_cpu:.4f} ± {std_server_cpu:.4f}, "
      f"Avg Energy: {avg_server_energy:.4f} ± {std_server_energy:.4f}")
print(f"Gateway → Avg CPU: {avg_gateway_cpu:.4f} ± {std_gateway_cpu:.4f}, "
      f"Avg Energy: {avg_gateway_energy:.4f} ± {std_gateway_energy:.4f}")

# --- Plotting ---
roles = ["Client", "Server", "Gateway"]

avg_energy_vals = [avg_client_energy, avg_server_energy, avg_gateway_energy]
std_energy_vals = [std_client_energy, std_server_energy, std_gateway_energy]

avg_cpu_vals = [avg_client_cpu, avg_server_cpu, avg_gateway_cpu]
std_cpu_vals = [std_client_cpu, std_server_cpu, std_gateway_cpu]

x = np.arange(len(roles))
width = 0.35

plt.figure(figsize=(10, 4))

# Energy plot
plt.subplot(1, 2, 1)
plt.bar(x, avg_energy_vals, yerr=std_energy_vals, capsize=5)
plt.xticks(x, roles)
plt.ylabel("Avg Energy (mJ)")
plt.title("Avg Energy per Role")
plt.grid(axis='y')

# CPU plot
plt.subplot(1, 2, 2)
plt.bar(x, avg_cpu_vals, yerr=std_cpu_vals, capsize=5, color='orange')
plt.xticks(x, roles)
plt.ylabel("Avg CPU Time (ms)")
plt.title("Avg CPU Time per Role")
plt.grid(axis='y')

plt.tight_layout()
plt.show()

