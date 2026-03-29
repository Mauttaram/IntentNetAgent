"""Synthetic tool: Create a VLAN on the managed switch."""
import asyncio


async def create_vlan(
    vlan_id: int,
    name: str,
    isolation: str = "standard",
    **kwargs,
) -> dict:
    """
    Provision a VLAN on the site's managed switch.

    Synthetic implementation — simulates a REST call to the switch management API.
    In production this would call the Cisco / Juniper / Ubiquiti API.
    """
    await asyncio.sleep(0.05)  # simulate network round-trip

    vlan_id = int(vlan_id)  # tolerate string inputs from plan step

    switch_ports = ["gi0/1", "gi0/2", "gi0/3"]
    if isolation == "strict":
        switch_ports.append("trunk-uplink-tagged")
    else:
        switch_ports.append("access-uplink-untagged")

    return {
        "status": "configured",
        "vlan_id": vlan_id,
        "name": name,
        "isolation": isolation,
        "switch_ports": switch_ports,
        "tagged_on_uplink": True,
        "device": "switch-floor-01",
        "config_applied": (
            f"interface range gi0/1-3\n"
            f" switchport mode access\n"
            f" switchport access vlan {vlan_id}\n"
            f"!\n"
            f"interface gi0/0 (uplink)\n"
            f" switchport mode trunk\n"
            f" switchport trunk allowed vlan add {vlan_id}"
        ),
    }
