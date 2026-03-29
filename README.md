# IntentNetAgent

Intent-Based Networking for SMBs — a domain-specific agent built on the [ScalableAgents](../ScalableAgents) framework.

> A coffee shop owner with no IT background says: *"I want internet connectivity to my Payment system and my Guest WiFi area."*
> The agent produces a PCI-DSS compliant, encrypted, segmented network — with the owner approving every decision before a single device is touched.

---

## What it does

IntentNetAgent translates plain-English network configuration requests into a safe, auditable, step-by-step execution plan and runs it against the site's hardware (or synthetic tools in demo mode).

```
Owner: "I want internet connectivity to my Payment system and my Guest WiFi area."
         │
         ▼
  [extract_intent]  →  action=configure_network  domain=networking  confidence=95%
         │
         ▼
  [extract_entities]  →  NetworkConfigEntity
                           payment_segment:  VLAN 10, isolation=strict, PCI_DSS
                           guest_segment:    VLAN 20, isolation=standard, internet_only
         │
         ▼
  [plan]  →  5-step DAG
         │
  ⏸ HITL Gate 1 — owner reviews network topology in plain English
         │  approve
         ▼
  [validate_cot]  →  Claude Opus 4.6 walks DAG; explains every dependency
         │
  ⏸ HITL Gate 2 — owner confirms agent's reasoning before any device is touched
         │  confirm
         ▼
  [executor_router]  →  Send API fan-out
         │
         ├── Tick 1: [create_payment_vlan] [create_guest_vlan]  ← parallel
         ├── Tick 2: [configure_firewall]
         ├── Tick 3: [setup_encryption]
         └── Tick 4: [apply_pci_compliance]
         │
         ▼
  [report]  →  Plan Execution Summary + PCI-DSS audit trail ID
```

---

## Demo LLM — `demo_llm.py`

`IntentNetDemoLLM` is a zero-dependency mock that replaces real Anthropic API calls so the demo runs without an API key, Postgres, or any network hardware.

### What it mocks

The ScalableAgents nodes call the LLM in two patterns. `IntentNetDemoLLM` implements both:

| Call pattern | Node | Returns |
|---|---|---|
| `llm.with_structured_output(Intent).ainvoke(msgs)` | `extract_intent` | `Intent(action="configure_network", domain="networking", confidence=0.95)` |
| `llm.with_structured_output(PlanResponse).ainvoke(msgs)` | `plan` | 5-step `PlanResponse` with full DAG wiring |
| `llm.with_structured_output(NetworkConfigEntity).ainvoke(msgs)` | `extract_entities` | `NetworkConfigEntity` with payment + guest segments |
| `llm.ainvoke(msgs)` | `validate_cot` | `AIMessage` containing the full CoT reasoning trace |

### Pre-baked CoT trace

The reasoning trace surfaced at HITL Gate 2 (hardcoded in `NETWORKING_COT_TRACE`):

```
Step create_payment_vlan: Create VLAN 10 for Payment Segment
  Depends on:  none — can start immediately

Step create_guest_vlan: Create VLAN 20 for Guest WiFi
  Depends on:  none — runs IN PARALLEL with create_payment_vlan

Step configure_firewall: Apply PCI-DSS Firewall Rules
  Depends on:  create_payment_vlan + create_guest_vlan
  Reason:      Firewall rules reference VLAN IDs that must already exist on the
               switch — applying ACLs before VLANs are provisioned would silently fail.

Step setup_encryption: Configure Encryption
  Depends on:  configure_firewall
  Reason:      Encryption must sit on top of a correctly segmented network.
               Configuring IPSec before firewall rules leaves a window where
               cross-VLAN traffic is routed but unencrypted.

Step apply_pci_compliance: Enforce PCI-DSS v4.0 Compliance Policy
  Depends on:  setup_encryption
  Reason:      Compliance policy is the final hardening layer — auditors require
               encryption to be in place before verifying cipher strength and logging.
```

### How the mock is wired

```python
# demo_llm.py
class _StructuredOutputWrapper:
    def __init__(self, schema: type) -> None:
        self._schema = schema

    async def ainvoke(self, messages) -> object:
        if self._schema is Intent:         return Intent(...)
        if self._schema is PlanResponse:   return PlanResponse(steps=[...])
        if self._schema is NetworkConfigEntity: return NetworkConfigEntity(...)

class IntentNetDemoLLM:
    def with_structured_output(self, schema):
        return _StructuredOutputWrapper(schema)     # ← structured output nodes

    async def ainvoke(self, messages):
        return AIMessage(content=NETWORKING_COT_TRACE)  # ← validate_cot

def make_demo_llm_config() -> LLMConfig:
    demo_llm = IntentNetDemoLLM()
    return LLMConfig(default_llm=demo_llm, reasoning_llm=demo_llm)
```

Injected into the graph via `config["configurable"]["llm_config"]` — the same slot used by real Anthropic models.

---

## Synthetic tools

All tool calls simulate network hardware APIs. No real devices are required.

| Tool | Simulates | Key output fields |
|---|---|---|
| `create_vlan` | REST call to managed switch | `vlan_id`, `switch_ports`, `config_applied` |
| `configure_firewall` | Firewall ACL push | `rules_applied` (6 ACL rules), `pci_dss_isolation_enforced` |
| `setup_encryption` | VPN gateway + AP controller | `payment_encryption` (IPSec), `guest_encryption` (WPA3) |
| `apply_pci_compliance` | Compliance policy engine | `checks_passed` (§1.3, §2.2, §6.3, §10.2), `audit_trail_id` |
| `verify_connectivity` | Network probe suite | 5 pass/fail tests across VLAN boundaries |

---

## Network entity schemas

`NetworkConfigEntity` is registered under `SCHEMA_REGISTRY["networking"]` so that `extract_entities` picks it up when `intent.domain == "networking"`.

```python
class NetworkSegmentEntity(EntityBase):
    name: str | None          # "payment" | "guest_wifi"
    vlan_id: int | None       # 10 | 20
    isolation: str | None     # "strict" | "standard"
    compliance: list[str]     # ["PCI_DSS"] | []
    access_policy: str | None # "pos_ports_only" | "internet_only"

class NetworkConfigEntity(EntityBase):
    site_name: str | None
    site_type: str | None     # "coffee_shop" | "restaurant" | "medical" | "retail"
    payment_segment: NetworkSegmentEntity | None
    guest_segment:   NetworkSegmentEntity | None
```

---

## Project structure

```
IntentNetAgent/
  pyproject.toml                    depends on ../ScalableAgents
  intent_net_agent/
    schemas/
      network_entities.py           NetworkSegmentEntity, NetworkConfigEntity
    tools/
      create_vlan.py                synthetic: provision VLAN on managed switch
      configure_firewall.py         synthetic: push PCI-DSS §1.3 ACLs
      setup_encryption.py           synthetic: IPSec tunnel + WPA3
      apply_pci_compliance.py       synthetic: TLS 1.2+, cipher policy, audit trail
      verify_connectivity.py        synthetic: 5-test connectivity probe suite
    demo_llm.py                     IntentNetDemoLLM + make_demo_llm_config()
    demo.py                         end-to-end demo runner
```

---

## Running the demo

```bash
# From AgenticFrmk/
cd IntentNetAgent
pip install -e "../ScalableAgents[dev]" -e ".[dev]"
python -m intent_net_agent.demo
```

No API key, no database, no network hardware required — everything is synthetic.

---

## How it extends ScalableAgents

IntentNetAgent adds a networking domain on top of the framework without modifying any framework code:

```python
# Register networking tools into the shared TOOL_REGISTRY
from scalable_agents.tools.registry import TOOL_REGISTRY
TOOL_REGISTRY["create_vlan"]          = create_vlan
TOOL_REGISTRY["configure_firewall"]   = configure_firewall
TOOL_REGISTRY["setup_encryption"]     = setup_encryption
TOOL_REGISTRY["apply_pci_compliance"] = apply_pci_compliance

# Register the networking entity schema so extract_entities resolves it
from scalable_agents.schemas.registry import SCHEMA_REGISTRY
SCHEMA_REGISTRY["networking"] = NetworkConfigEntity
```

The same pattern works for any vertical: medical offices (HIPAA segmentation), retail chains (POS isolation), restaurants (kitchen/POS/guest separation) — register different schemas and tools, reuse the entire framework.
