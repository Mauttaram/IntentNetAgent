"""Synthetic tool: Apply PCI-DSS inter-VLAN firewall rules."""
import asyncio


async def configure_firewall(
    payment_vlan_id: int = 10,
    guest_vlan_id: int = 20,
    **kwargs,
) -> dict:
    """
    Push firewall ACLs enforcing PCI-DSS §1.3 network isolation.

    Rules applied:
    - Block all traffic between payment and guest VLANs (both directions)
    - Allow payment VLAN only to POS processor on TCP 443/8443
    - Allow guest VLAN outbound internet (TCP 80/443) only; block RFC1918

    Synthetic implementation — simulates firewall API push.
    """
    await asyncio.sleep(0.08)

    payment_vlan_id = int(payment_vlan_id)
    guest_vlan_id = int(guest_vlan_id)

    rules = [
        {
            "seq": 10,
            "action": "DENY",
            "src": f"vlan{payment_vlan_id}",
            "dst": f"vlan{guest_vlan_id}",
            "proto": "any",
            "reason": "PCI-DSS §1.3: isolate cardholder data environment",
        },
        {
            "seq": 20,
            "action": "DENY",
            "src": f"vlan{guest_vlan_id}",
            "dst": f"vlan{payment_vlan_id}",
            "proto": "any",
            "reason": "PCI-DSS §1.3: prevent lateral movement from guest to payment",
        },
        {
            "seq": 30,
            "action": "ALLOW",
            "src": f"vlan{payment_vlan_id}",
            "dst": "payment-processor.example.com",
            "proto": "TCP",
            "ports": [443, 8443],
            "reason": "Allow POS traffic to payment processor only",
        },
        {
            "seq": 40,
            "action": "DENY",
            "src": f"vlan{guest_vlan_id}",
            "dst": "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16",
            "proto": "any",
            "reason": "Block guest access to all RFC1918 private networks",
        },
        {
            "seq": 50,
            "action": "ALLOW",
            "src": f"vlan{guest_vlan_id}",
            "dst": "0.0.0.0/0",
            "proto": "TCP",
            "ports": [80, 443],
            "reason": "Allow guest internet browsing only",
        },
        {
            "seq": 60,
            "action": "DENY",
            "src": "any",
            "dst": "any",
            "proto": "any",
            "reason": "Implicit deny all",
        },
    ]

    return {
        "status": "configured",
        "device": "fw-edge-01",
        "rules_applied": rules,
        "rule_count": len(rules),
        "pci_dss_isolation_enforced": True,
        "acl_name": "INTENT-NET-ACL-001",
    }
