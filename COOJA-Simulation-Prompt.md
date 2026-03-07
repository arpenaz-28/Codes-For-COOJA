# COOJA IoT Authentication Scheme — Full Pipeline Prompt

Use this prompt in a new chat to replicate the entire simulation + paper workflow for any authentication scheme.

---

## Paste this into a new chat:

---

I want you to implement and simulate an IoT authentication scheme using **COOJA on Contiki-NG** running inside **Docker on Windows**, then generate a formatted academic paper. Do everything end-to-end with minimal back-and-forth.

### Step 1: Read the Scheme Paper

Read the PDF at: `c:\ANUP\MTP\<SCHEME_FOLDER>\<paper-name>.pdf`
*(Use pymupdf to extract text — `read_file` won't work on binary PDFs.)*

Understand all protocol phases, message flows, and cryptographic operations.

### Step 2: Write the Contiki-NG Source Code

Create the project at: `c:\ANUP\MTP\Proposing\Codes For COOJA\<SCHEME_NAME>\`

Required files:
- **device-node.c** — IoT device (CoAP client): enrollment, authentication, data transmission
- **as-node.c** — Authentication Server (CoAP server + client): handles registration, auth verification, key exchange, forwards tokens to GW
- **gw-node.c** — Gateway (RPL root, CoAP server): processes auth tokens, decrypts data
- **aes.c / aes.h** — AES-128-ECB (reuse from `c:\ANUP\MTP\Proposing\Codes For COOJA\Current\aes.c`)
- **sha256.c / sha256.h** — SHA-256 (reuse from `c:\ANUP\MTP\Proposing\Codes For COOJA\Current\sha256.c`)
- **project-conf.h** — Must include `ENERGEST_CONF_ON 1` (critical for energy measurement)
- **Makefile** — Contiki-NG build targeting `cooja`

Follow these conventions:
- GW = Node ID 1, AS = Node ID 2, Devices = Node ID 3+
- Use CoAP over RPL for all communication
- Device flow: Reg-0 → Reg-1 → Auth → Data loop
- Include Energest snapshots: capture CPU/energy ticks before and after the auth+data block, print as `AUTH_ENERGY|<node_id>|cpu_ticks=...|energy_ticks=...|cpu_s=...|energy_j=...`
- Energy constants: 3.0V supply, CPU=1.8mA, LPM=0.0545mA, TX=17.4mA, RX=18.8mA

### Step 3: Docker + Build

```powershell
# Reload PATH if docker not found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

# Create container (if not exists)
docker run -d --name cooja-sim -v "c:\ANUP\MTP\Proposing\Codes For COOJA\<SCHEME_NAME>:/opt/contiki-ng/examples/myproject" contiker/contiki-ng tail -f /dev/null

# Build firmware
docker exec cooja-sim bash -c "cd /opt/contiki-ng/examples/myproject && make TARGET=cooja"

# Verify build
docker exec cooja-sim bash -c "ls -la /opt/contiki-ng/examples/myproject/build/cooja/*.cooja"
```

### Step 4: Create CSC File & Run Simulation

Create a `.csc` file with:
- 100 nodes: 1 GW + 79 AS + 20 Devices
- 10×10 grid, 30-unit spacing
- UDGM propagation model
- 1800s simulation time
- Use `<script>` with TIMEOUT (NOT `<plugin>ScriptRunner`)
- `<simconf>` as XML root

Run headless:
```powershell
docker exec cooja-sim bash -c "cd /opt/contiki-ng/tools/cooja && ./gradlew --no-watch-fs run --args='--no-gui --contiki=/opt/contiki-ng --autostart /opt/contiki-ng/examples/myproject/<sim>.csc'" 2>&1 | Select-Object -Last 200
```

### Step 5: Export Results

Parse simulation output for `AUTH_ENERGY` lines → create `simulation-results.csv` with columns: Device_ID, CPU_Ticks, Energy_Ticks, CPU_Time_s, Energy_J

### Step 6: Generate Academic Paper

Create a Python script (`generate_paper.py`) using `python-docx` + `matplotlib` to generate a Word document with:
- **Sequence diagrams** (matplotlib) for each protocol phase
- **System architecture** diagram
- IEEE-style sections: Abstract, Introduction, System Model, Prerequisites, Proposed Scheme (with sub-phases), Security Analysis, Performance Analysis, Conclusion, References
- **Tables**: Notations, Implementation Parameters, CoAP Endpoints, Simulation Parameters, Protocol Summary, Per-device Energy, Computational Cost Comparison, Communication Cost Comparison
- Style: dark blue headers (#1A3C6E), green highlight on proposed scheme rows, Calibri font

Python setup:
```powershell
# Create venv + install deps
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pymupdf python-docx matplotlib
```

### Step 7: Git + Push

```powershell
git init
git add .
git commit -m "Initial commit: <SCHEME_NAME> COOJA implementation"
git remote add origin https://arpenaz-28@github.com/arpenaz-28/<REPO_NAME>.git
git branch -M main
git push -u origin main
```

Also create a nice README.md with: scheme overview, protocol phase table, project structure, simulation results, security properties, and build instructions.

### Known Gotchas (already solved — don't waste time on these):
1. **Docker PATH missing** after restart → reload with `$env:PATH = ...` command above
2. **CSC file** must use `<script>` with TIMEOUT, NOT `<plugin>ScriptRunner`
3. **Energest returns 0** if you forget `#define ENERGEST_CONF_ON 1` in project-conf.h
4. **PDF reading** fails with read_file → use pymupdf extraction script
5. **PowerShell multiline Python** doesn't work → create `.py` file and run it
6. **GW initial rejections** are normal (race condition) — devices retry automatically

---

### FILL IN BEFORE PASTING:
- `<SCHEME_FOLDER>`: folder containing the scheme's base paper PDF
- `<paper-name>.pdf`: the PDF filename
- `<SCHEME_NAME>`: name for the new project folder
- `<REPO_NAME>`: GitHub repository name
