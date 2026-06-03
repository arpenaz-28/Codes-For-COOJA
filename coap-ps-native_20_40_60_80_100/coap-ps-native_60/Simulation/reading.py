import re

def parse_energest(file_path):
    with open(file_path, 'r') as f:
        data = f.read()

    # Extract all energest lines
    energest_entries = re.findall(
        r"Estimated Energy", data)

    if len(energest_entries) < 2:
        print("Not enough readings. Need both full (Reg+Auth+Data) and reduced (Auth+Data) entries.")
        return

    # Convert to integers
    full = list(map(int, energest_entries[0]))  # Reg + Auth + Data
    reduced = list(map(int, energest_entries[1]))  # Auth + Data

    print("---- Energest Readings ----")
    print(f"Full (Reg+Auth+Data): {full}")
    print(f"Reduced (Auth+Data): {reduced}")

    # Calculate the difference (i.e., registration overhead)
    diff = [f - r for f, r in zip(full, reduced)]
    cpu_diff = diff[0]
    energy_diff = sum(diff[3:])  # TX + RX (radio energy)

    print("\n---- Overhead Due to Registration ----")
    print(f"CPU cycles: {cpu_diff}")
    print(f"Energy (TX + RX): {energy_diff} ticks")

    return cpu_diff, energy_diff

# Example usage
if __name__ == "__main__":
    path_to_log = "100(Single Auth +data).log"  # Replace with your log file from Cooja
    parse_energest(path_to_log)

