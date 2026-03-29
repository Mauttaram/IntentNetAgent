"""
IntentNetDemoLLM — a zero-dependency mock LLM for the IntentNetAgent demo.

Replaces real Anthropic API calls with pre-configured networking responses so
the demo runs without an API key, Postgres, or any external services.

All responses are drawn from the coffee-shop scenario in HACKATHON.md:
  "I want internet connectivity to my Payment system and my Guest WiFi area."
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from scalable_agents.llm.config import LLMConfig
from scalable_agents.schemas.intent import Intent
from intent_net_agent.schemas.network_entities import (
    NetworkConfigEntity,
    NetworkSegmentEntity,
)


# ---------------------------------------------------------------------------
# Pre-baked networking CoT trace (surfaced to the owner at HITL gate 2)
# ---------------------------------------------------------------------------
NETWORKING_COT_TRACE = """\
Step create_payment_vlan: Create VLAN 10 for Payment Segment
  Description: Provision VLAN 10 on the managed switch for the PCI-DSS
               cardholder data environment (CDE).
  Depends on:  none — can start immediately
  Expected output: VLAN 10 configured on switch ports; tagged on trunk uplink

Step create_guest_vlan: Create VLAN 20 for Guest WiFi
  Description: Provision VLAN 20 for guest internet access, fully isolated
               from the payment network.
  Depends on:  none — runs IN PARALLEL with create_payment_vlan
  Expected output: VLAN 20 configured on switch ports; tagged on trunk uplink

Step configure_firewall: Apply PCI-DSS Firewall Rules
  Description: Push inter-VLAN ACLs enforcing PCI-DSS §1.3 network isolation:
               payment↔guest blocked in both directions; guest restricted to
               internet-only (TCP 80/443); payment allowed only to POS processor.
  Depends on:  create_payment_vlan + create_guest_vlan
  Reason:      Firewall rules reference VLAN IDs that must already exist on
               the switch — applying ACLs before VLANs are provisioned would
               silently fail on most managed-switch OSes.
  Expected output: 6 ACL rules applied; PCI-DSS isolation enforced

Step setup_encryption: Configure Encryption
  Description: IPSec IKEv2/AES-256-GCM tunnel to payment processor; WPA3
               with mandatory PMF and client isolation for guest WiFi.
  Depends on:  configure_firewall
  Reason:      Encryption must be layered on top of a correctly segmented
               network. Configuring IPSec before firewall rules creates a
               window where cross-VLAN traffic is routed but unencrypted.
  Expected output: Payment: IPSec tunnel UP; Guest: WPA3-Personal SSID active

Step apply_pci_compliance: Enforce PCI-DSS v4.0 Compliance Policy
  Description: Enforce TLS 1.2+ minimum; disable RC4/DES/3DES/export ciphers;
               enable full traffic logging (syslog forwarding).
  Depends on:  setup_encryption
  Reason:      Compliance policy is the final hardening layer — auditors
               require that encryption is in place before verifying cipher
               strength, and that logging is running on live traffic.
  Expected output: 4 PCI-DSS v4.0 requirements satisfied; audit trail ID issued\
"""


# ---------------------------------------------------------------------------
# Mock structured-output wrapper
# ---------------------------------------------------------------------------
class _StructuredOutputWrapper:
    """Returns the correct pre-built object for the schema requested."""

    def __init__(self, schema: type) -> None:
        self._schema = schema

    async def ainvoke(self, messages) -> object:  # noqa: ANN001
        # Import inside method to avoid circular-import at module load time
        from scalable_agents.nodes.plan import PlanResponse
        from scalable_agents.schemas.plan import Step

        if self._schema is Intent:
            return Intent(
                action="configure_network",
                domain="networking",
                confidence=0.95,
                ambiguous=False,
            )

        if self._schema is PlanResponse:
            return PlanResponse(
                steps=[
                    Step(
                        id="create_payment_vlan",
                        name="Create Payment VLAN",
                        description=(
                            "Provision VLAN 10 on the managed switch for the PCI-DSS "
                            "cardholder data environment"
                        ),
                        tool_name="create_vlan",
                        dependencies=[],
                        expected_output="VLAN 10 configured; tagged on trunk uplink",
                        critical=True,
                        inputs={"vlan_id": 10, "name": "payment", "isolation": "strict"},
                    ),
                    Step(
                        id="create_guest_vlan",
                        name="Create Guest WiFi VLAN",
                        description=(
                            "Provision VLAN 20 for guest internet access, isolated from "
                            "the payment network"
                        ),
                        tool_name="create_vlan",
                        dependencies=[],
                        expected_output="VLAN 20 configured; tagged on trunk uplink",
                        critical=True,
                        inputs={"vlan_id": 20, "name": "guest_wifi", "isolation": "standard"},
                    ),
                    Step(
                        id="configure_firewall",
                        name="Configure Firewall Rules",
                        description=(
                            "Apply PCI-DSS §1.3 inter-VLAN isolation ACLs: "
                            "payment↔guest blocked; payment→POS only; guest→internet only"
                        ),
                        tool_name="configure_firewall",
                        dependencies=["create_payment_vlan", "create_guest_vlan"],
                        expected_output="6 ACL rules applied; PCI-DSS isolation enforced",
                        critical=True,
                        inputs={"payment_vlan_id": 10, "guest_vlan_id": 20},
                    ),
                    Step(
                        id="setup_encryption",
                        name="Setup Encryption",
                        description=(
                            "IPSec IKEv2/AES-256-GCM tunnel for payment traffic; "
                            "WPA3 + client isolation for guest WiFi"
                        ),
                        tool_name="setup_encryption",
                        dependencies=["configure_firewall"],
                        expected_output=(
                            "Payment: IPSec tunnel active (AES-256-GCM); "
                            "Guest: WPA3-Personal with mandatory PMF"
                        ),
                        critical=True,
                        inputs={"payment_vlan_id": 10, "guest_vlan_id": 20},
                    ),
                    Step(
                        id="apply_pci_compliance",
                        name="Apply PCI-DSS Compliance",
                        description=(
                            "Enforce TLS 1.2+, disable weak ciphers, enable full traffic "
                            "logging per PCI-DSS v4.0 §1.3, §2.2, §6.3, §10.2"
                        ),
                        tool_name="apply_pci_compliance",
                        dependencies=["setup_encryption"],
                        expected_output=(
                            "All 4 PCI-DSS v4.0 checks passed; audit trail ID issued"
                        ),
                        critical=True,
                        inputs={"vlan_id": 10},
                    ),
                ]
            )

        if self._schema is NetworkConfigEntity:
            return NetworkConfigEntity(
                site_name="Blue Bottle Coffee — Valencia St",
                site_type="coffee_shop",
                payment_segment=NetworkSegmentEntity(
                    name="payment",
                    vlan_id=10,
                    isolation="strict",
                    compliance=["PCI_DSS"],
                    access_policy="pos_ports_only",
                ),
                guest_segment=NetworkSegmentEntity(
                    name="guest_wifi",
                    vlan_id=20,
                    isolation="standard",
                    compliance=[],
                    access_policy="internet_only",
                ),
            )

        raise ValueError(
            f"IntentNetDemoLLM: no mock response configured for schema '{self._schema.__name__}'"
        )


# ---------------------------------------------------------------------------
# Public mock LLM
# ---------------------------------------------------------------------------
class IntentNetDemoLLM:
    """
    Drop-in replacement for a real ChatAnthropic model.

    Implements the two call patterns used by ScalableAgents nodes:
      - with_structured_output(schema).ainvoke(messages)  — intent, plan, entities
      - ainvoke(messages)                                  — CoT trace (validate_cot)
    """

    def with_structured_output(self, schema: type) -> _StructuredOutputWrapper:
        return _StructuredOutputWrapper(schema)

    async def ainvoke(self, messages) -> AIMessage:
        """Return the pre-built CoT reasoning trace (used by validate_cot node)."""
        return AIMessage(content=NETWORKING_COT_TRACE)


def make_demo_llm_config() -> LLMConfig:
    """Return an LLMConfig wired with IntentNetDemoLLM for both default and reasoning slots."""
    demo_llm = IntentNetDemoLLM()
    return LLMConfig(default_llm=demo_llm, reasoning_llm=demo_llm)
