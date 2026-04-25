"""
Network entity schemas for the IntentNetAgent.

These extend AgentCore' EntityBase and are registered in SCHEMA_REGISTRY
under the "networking" domain key so that extract_entities picks them up when
intent.domain == "networking".
"""
from __future__ import annotations
from pydantic import Field
from agentcore.schemas.entity import EntityBase


class NetworkSegmentEntity(EntityBase):
    """A named network segment — payment zone, guest WiFi area, IoT segment, etc."""
    name: str | None = None
    vlan_id: int | None = None
    isolation: str | None = None          # strict | standard | open
    compliance: list[str] | None = None   # ["PCI_DSS"], ["HIPAA"], []
    access_policy: str | None = None      # pos_ports_only | internet_only | full


class NetworkConfigEntity(EntityBase):
    """Top-level entity extracted from a network configuration request."""
    site_name: str | None = None
    site_type: str | None = None          # coffee_shop | restaurant | medical | retail
    payment_segment: NetworkSegmentEntity | None = None
    guest_segment: NetworkSegmentEntity | None = None
