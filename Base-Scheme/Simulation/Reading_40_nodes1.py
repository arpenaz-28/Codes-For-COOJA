import re
import matplotlib.pyplot as plt
import numpy as np

# Replace this with your actual log file name
log_file_path = "40(Single Auth +data)1.txt"

# Store: client_id → {client: {energy, cpu}, server: {...}, gateway: {...}}
auth_data = {}

with open(log_file_path, "r") as f:
    for line in f:
        # Match client log
        client_match = re.search(
            r"ID:(\d+).*for client (\d+) are (\d+\.\d+) and (\d+\.\d+)", line)
        if client_match:
            client_id = int(client_match.group(2))
            cpu = float(client_match.group(3))
            energy = float(client_match.group(4))

            if client_id not in auth_data:
                auth_data[client_id] = {}
            auth_data[client_id]['client'] = {'cpu': cpu, 'energy': energy}
            continue

        # Match server log
        server_match = re.search(
            r"ID:(\d+).*for client (\d+) by server (\d+) is (\d+\.\d+) and (\d+\.\d+)", line)
        if server_match:
            client_id = int(server_match.group(2))
            cpu = float(server_match.group(4))
            energy = float(server_match.group(5))

            if client_id not in auth_data:
                auth_data[client_id] = {}
            auth_data[client_id]['server'] = {'cpu': cpu, 'energy': energy}
            continue

        # Match gateway log
        gateway_match = re.search(
            r"ID:(\d+).*for client (\d+) by server (\d+) and gateway (\d+) are (\d+\.\d+) and (\d+\.\d+)", line)
        if gateway_match:
            client_id = int(gateway_match.group(2))
            cpu = float(gateway_match.group(5))
            energy = float(gateway_match.group(6))

            if client_id not in auth_data:
                auth_data[client_id] = {}
            auth_data[client_id]['gateway'] = {'cpu': cpu, 'energy': energy}
            continue

# --- Compute Average Energy and CPU Time ---
total_energy_vals = []
total_cpu_vals = []

for client_id, roles in auth_data.items():
    if all(role in roles for role in ['client', 'server', 'gateway']):
        total_energy = roles['client']['energy'] + roles['server']['energy'] + roles['gateway']['energy']
        total_cpu = roles['client']['cpu'] + roles['server']['cpu'] + roles['gateway']['cpu']

        total_energy_vals.append(total_energy)
        total_cpu_vals.append(total_cpu)
    else:
        print(f"⚠️ Incomplete data for client {client_id}: {roles}")

if total_energy_vals and total_cpu_vals:
    avg_energy = np.mean(total_energy_vals)
    std_energy = np.std(total_energy_vals)

    avg_cpu = np.mean(total_cpu_vals)
    std_cpu = np.std(total_cpu_vals)

    print(f"\n✅ Average Energy per Authentication: {avg_energy:.4f} mJ ± {std_energy:.4f}")
    print(f"✅ Average CPU Time per Authentication: {avg_cpu:.4f} ms ± {std_cpu:.4f}")
else:
    print("\n❌ No complete authentication records found.")

# ---- Plotting ----
node_counts = [8]  # Replace with actual number of nodes
plt.figure(figsize=(10, 4))

# Energy Plot
plt.subplot(1, 2, 1)
plt.bar(node_counts, [avg_energy], yerr=[std_energy], capsize=5)
plt.xlabel("Number of Nodes")
plt.ylabel("Avg Energy (mJ)")
plt.title("Energy vs Number of Nodes")
plt.grid(axis='y')

# CPU Plot
plt.subplot(1, 2, 2)
plt.bar(node_counts, [avg_cpu], yerr=[std_cpu], capsize=5)
plt.xlabel("Number of Nodes")
plt.ylabel("Avg CPU Time (ms)")
plt.title("CPU Time vs Number of Nodes")
plt.grid(axis='y')

plt.tight_layout()
plt.show()

