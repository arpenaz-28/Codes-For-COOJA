"""Generate 100-node CSC simulation file for Base Scheme (unified build)."""
lines = []
lines.append('<?xml version="1.0" encoding="UTF-8"?>')
lines.append('<simconf version="2022112801">')
lines.append('  <simulation>')
lines.append('    <title>Base Scheme 100 Nodes (1GW + 79AS + 20Dev)</title>')
lines.append('    <randomseed>123456</randomseed>')
lines.append('    <motedelay_us>1000000</motedelay_us>')
lines.append('    <radiomedium>')
lines.append('      org.contikios.cooja.radiomediums.UDGM')
lines.append('      <transmitting_range>150.0</transmitting_range>')
lines.append('      <interference_range>200.0</interference_range>')
lines.append('      <success_ratio_tx>1.0</success_ratio_tx>')
lines.append('      <success_ratio_rx>1.0</success_ratio_rx>')
lines.append('    </radiomedium>')
lines.append('    <events>')
lines.append('      <logoutput>40000</logoutput>')
lines.append('    </events>')

IFACES = """      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Battery</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiVib</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiBeeper</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiButton</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiPIR</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiLED</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiCFS</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>"""

def mote_block(node_id, x, y):
    return f"""      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="{x}" y="{y}" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>{node_id}</id>
        </interface_config>
      </mote>"""

# --- GW (node 1) ---
lines.append('    <motetype>')
lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
lines.append('      <description>GW Node</description>')
lines.append('      <source>[CONTIKI_DIR]/examples/myproject/gw-node.c</source>')
lines.append('      <commands>$(MAKE) -j$(CPUS) gw-node.cooja TARGET=cooja</commands>')
lines.append('      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/gw-node.cooja</firmware>')
lines.append(IFACES)
lines.append(mote_block(1, 0, 0))
lines.append('    </motetype>')

# --- AS (nodes 2-80) ---
lines.append('    <motetype>')
lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
lines.append('      <description>AS Node</description>')
lines.append('      <source>[CONTIKI_DIR]/examples/myproject/as-node.c</source>')
lines.append('      <commands>$(MAKE) -j$(CPUS) as-node.cooja TARGET=cooja</commands>')
lines.append('      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/as-node.cooja</firmware>')
lines.append(IFACES)
for nid in range(2, 81):
    row = (nid - 2) // 10
    col = (nid - 2) % 10
    lines.append(mote_block(nid, col * 30, 30 + row * 30))
lines.append('    </motetype>')

# --- Device (nodes 81-100) ---
lines.append('    <motetype>')
lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
lines.append('      <description>Device Node</description>')
lines.append('      <source>[CONTIKI_DIR]/examples/myproject/device-node.c</source>')
lines.append('      <commands>$(MAKE) -j$(CPUS) device-node.cooja TARGET=cooja</commands>')
lines.append('      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/device-node.cooja</firmware>')
lines.append(IFACES)
for nid in range(81, 101):
    row = (nid - 81) // 5
    col = (nid - 81) % 5
    lines.append(mote_block(nid, 60 + col * 30, 300 + row * 30))
lines.append('    </motetype>')

# Plugins for headless run
lines.append('  </simulation>')
lines.append('  <plugin>')
lines.append('    org.contikios.cooja.plugins.LogListener')
lines.append('    <plugin_config>')
lines.append('      <filter />')
lines.append('      <formatted_time />')
lines.append('      <coloring />')
lines.append('    </plugin_config>')
lines.append('    <bounds x="400" y="1" height="400" width="800" z="1" />')
lines.append('  </plugin>')
lines.append('  <plugin>')
lines.append('    org.contikios.cooja.plugins.ScriptRunner')
lines.append('    <plugin_config>')
lines.append('      <script>')
lines.append('TIMEOUT(1800000, log.testOK());')
lines.append('while(true) {')
lines.append('  log.log(time + " " + id + " " + msg + "\\n");')
lines.append('  YIELD();')
lines.append('}')
lines.append('      </script>')
lines.append('      <active>true</active>')
lines.append('    </plugin_config>')
lines.append('    <bounds x="0" y="600" height="300" width="600" z="3" />')
lines.append('  </plugin>')
lines.append('</simconf>')

with open(r"c:\ANUP\MTP\Proposing\Codes For COOJA\Base-Scheme\test-sim-100.csc", "w") as f:
    f.write("\n".join(lines))
print("Generated test-sim-100.csc")
