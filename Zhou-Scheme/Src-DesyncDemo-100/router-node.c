/* router-node.c — Minimal RPL router for 100-node Zhou desync topology.
 * Nodes 2–80: participate in RPL routing only; no auth logic. */

#include "contiki.h"
#include "net/routing/routing.h"

PROCESS(router_node, "Router Node");
AUTOSTART_PROCESSES(&router_node);

PROCESS_THREAD(router_node, ev, data)
{
    PROCESS_BEGIN();
    while (1) {
        PROCESS_YIELD();
    }
    PROCESS_END();
}
