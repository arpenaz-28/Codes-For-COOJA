import re
import matplotlib.pyplot as plt
import numpy as np

# Replace this with your actual log file name
log_file_path = "10(Single Auth +data)1.txt"

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

      

# --- Compute Average Energy and CPU Time ---
total_energy_vals = []
total_cpu_vals = []

for client_id, roles in auth_data.items():
    if all(role in roles for role in ['client']):
        total_energy = roles['client']['energy'] 
        total_cpu = roles['client']['cpu'] 

        total_energy_vals.append(total_energy)
        total_cpu_vals.append(total_cpu)
    else:
        print(f"⚠️ Incomplete data for client {client_id}: {roles}")

if total_energy_vals and total_cpu_vals:
    avg_energy = np.sum(total_energy_vals)
  #  std_energy = np.std(total_energy_vals)

    avg_cpu = np.sum(total_cpu_vals)
  #std_cpu = np.std(total_cpu_vals)

    print(f"\n✅ Total Energy per Authentication: {avg_energy:.4f} mJ")
    print(f"✅ Total CPU Time per Authentication: {avg_cpu:.4f} ms")
else:
    print("\n❌ No complete authentication records found.")



