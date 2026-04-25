"""
IntentNetAgent Demo
===================
Intent-Based Networking for SMBs — powered by ScalableAgents Framework.

Scenario
--------
A coffee shop owner with no IT background tells the agent:

    "I want internet connectivity to my Payment system and my Guest WiFi area."

The agent:
  1. Extracts the networking intent (confidence 0.95, domain=networking)
  2. Extracts typed entities  (NetworkConfigEntity with two NetworkSegmentEntity)
  3. Builds a 5-step DAG plan with automatic parallelism detection
  4. Pauses at HITL gate 1 — owner reviews the full network topology
  5. Generates a CoT reasoning trace (claude-opus-4-6 walks the DAG)
  6. Pauses at HITL gate 2 — owner confirms the agent's reasoning
  7. Executes steps in DAG order (steps 1+2 run in parallel)
  8. Generates a final compliance report

All tool calls are synthetic. No API key, database, or network hardware required.

Usage
-----
    # From AgenticFrmk/IntentNetAgent/
    pip install -e "../ScalableAgents[dev]" -e ".[dev]"
    python -m intent_net_agent.demo
"""
from __future__ import annotations

import asyncio
import sys
import textwrap
import warnings
from pathlib import Path

# Suppress LangGraph checkpoint deserialisation warnings — not relevant for the demo
warnings.filterwarnings("ignore", message="Deserializing unregistered type")

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

# ---------------------------------------------------------------------------
# Bootstrap: ensure ScalableAgents is importable when running from source
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[2]
_scalable_agents_src = _repo_root / "ScalableAgents"
if str(_scalable_agents_src) not in sys.path:
    sys.path.insert(0, str(_scalable_agents_src))

# ---------------------------------------------------------------------------
# Register IntentNet tools and schema into ScalableAgents' global registries
# ---------------------------------------------------------------------------
from agentcore.tools.registry import TOOL_REGISTRY          # noqa: E402
from agentcore.schemas.registry import SCHEMA_REGISTRY      # noqa: E402

from intent_net_agent.tools.create_vlan import create_vlan                    # noqa: E402
from intent_net_agent.tools.configure_firewall import configure_firewall      # noqa: E402
from intent_net_agent.tools.setup_encryption import setup_encryption          # noqa: E402
from intent_net_agent.tools.apply_pci_compliance import apply_pci_compliance  # noqa: E402
from intent_net_agent.tools.verify_connectivity import verify_connectivity    # noqa: E402
from intent_net_agent.schemas.network_entities import NetworkConfigEntity     # noqa: E402

TOOL_REGISTRY["create_vlan"] = create_vlan
TOOL_REGISTRY["configure_firewall"] = configure_firewall
TOOL_REGISTRY["setup_encryption"] = setup_encryption
TOOL_REGISTRY["apply_pci_compliance"] = apply_pci_compliance
TOOL_REGISTRY["verify_connectivity"] = verify_connectivity
SCHEMA_REGISTRY["networking"] = NetworkConfigEntity

# ---------------------------------------------------------------------------
# Framework imports (after path fixup)
# ---------------------------------------------------------------------------
from agentcore.graph.builder import build_graph              # noqa: E402
from intent_net_agent.demo_llm import make_demo_llm_config         # noqa: E402


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"
RED     = "\033[91m"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def out(text: str = "") -> None:
    print(text, flush=True)


def section(title: str, color: str = CYAN) -> None:
    bar = "─" * 72
    out(f"\n{_c(bar, color)}")
    out(f"{_c(f'  {title}', BOLD + color)}")
    out(f"{_c(bar, color)}")


def bullet(label: str, value: str, indent: int = 4) -> None:
    pad = " " * indent
    out(f"{pad}{_c(label, DIM)}  {value}")


def pause_banner(gate: int, prompt: str) -> None:
    bar = "═" * 72
    out(f"\n{_c(bar, YELLOW)}")
    out(f"  {_c(f'⏸  HITL Gate {gate}: {prompt}', BOLD + YELLOW)}")
    out(f"{_c(bar, YELLOW)}")


async def p(secs: float) -> None:
    """Pacing pause — gives the audience time to read before moving on."""
    await asyncio.sleep(secs)


# ---------------------------------------------------------------------------
# Pretty-printers for each phase
# ---------------------------------------------------------------------------
async def print_plan(state: dict) -> None:
    plan = state.get("plan")
    if plan is None:
        return
    out()
    for i, step in enumerate(plan.steps, 1):
        deps = (
            _c("  (parallel — no deps)", GREEN)
            if not step.dependencies
            else _c(f"  (after: {', '.join(step.dependencies)})", DIM)
        )
        out(f"    {_c(str(i) + '.', BOLD)} {_c(step.name, BOLD)}{deps}")
        out(f"       {step.description}")
        out(f"       {_c('tool:', DIM)} {step.tool_name}  "
            f"{_c('inputs:', DIM)} {step.inputs}")
        out()
        await p(0.4)


async def print_cot_trace(trace: str) -> None:
    if not trace:
        return
    out()
    for para in trace.strip().split("\n\n"):
        lines = para.splitlines()
        if lines:
            out(f"    {_c(lines[0], BOLD + CYAN)}")
            for line in lines[1:]:
                out(f"    {line}")
        out()
        await p(0.7)


async def print_execution_results(state: dict) -> None:
    plan = state.get("plan")
    step_results = state.get("step_results", {})
    if plan is None:
        return
    out()
    for step in plan.steps:
        result = step_results.get(step.id)
        if result is None:
            out(f"    {_c('?', YELLOW)} {step.name}  {_c('(no result)', DIM)}")
        elif result.status == "completed":
            out_data = result.output or {}
            summary = out_data.get("status", "ok")
            out(f"    {_c('✓', GREEN)} {_c(step.name, BOLD)}  {_c(f'[{summary}]', GREEN)}")
            for k, v in list(out_data.items())[:3]:
                if k == "status":
                    continue
                v_str = str(v)[:80] + ("…" if len(str(v)) > 80 else "")
                out(f"      {_c(k + ':', DIM)} {v_str}")
        elif result.status == "failed":
            out(f"    {_c('✗', RED)} {step.name}  {_c('FAILED: ' + (result.error or ''), RED)}")
        elif result.status == "skipped":
            out(f"    {_c('-', DIM)} {step.name}  {_c('skipped', DIM)}")
        await p(0.35)
    out()


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------
USER_MESSAGE = (
    "I want internet connectivity to my Payment system and my Guest WiFi area."
)

HITL_PLAN_REVIEW = textwrap.dedent("""\
    Here is the network I am about to configure:

    1. Payment VLAN (VLAN 10) — strict isolation, PCI-DSS compliant
       Ports allowed: TCP 443/8443 to your payment processor only

    2. Guest WiFi VLAN (VLAN 20) — standard isolation
       Ports allowed: TCP 80/443 to internet; all RFC1918 blocked

    Steps 1 and 2 run in PARALLEL (no dependency between them).

    3. Firewall rules applied after both VLANs exist
    4. Encryption layered on top of the firewall rules
    5. PCI-DSS compliance policy applied last

    Do you approve this plan? [approve / reject / modify <changes>]
""")


async def run_demo() -> None:
    # ── Header ─────────────────────────────────────────────────────────────
    out(f"\n{_c('=' * 72, BOLD + MAGENTA)}")
    out(f"  {_c('IntentNetAgent — Intent-Based Networking for SMBs', BOLD + MAGENTA)}")
    out(f"  {_c('Powered by ScalableAgents Framework', DIM)}")
    out(f"{_c('=' * 72, BOLD + MAGENTA)}\n")
    out(f"  Scenario: Coffee shop owner configures a PCI-DSS compliant network")
    out(f"  No IT knowledge required — plain English is the interface.\n")
    await p(2.0)

    # ── Graph setup (silent) ────────────────────────────────────────────────
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    llm_config = make_demo_llm_config()
    config: dict = {
        "configurable": {
            "thread_id": "intentnet-demo-001",
            "llm_config": llm_config,
        }
    }

    # ====================================================================
    # PHASE 1  User submits request → extract_intent → plan → HITL gate 1
    # ====================================================================
    section("PHASE 1  User submits request")
    await p(0.8)
    out(f"\n  {_c('Owner:', BOLD + GREEN)} \"{USER_MESSAGE}\"\n")
    await p(1.2)

    out(f"  {_c('  ...thinking...', DIM)}")
    await p(0.5)

    state = await graph.ainvoke(
        {"messages": [HumanMessage(content=USER_MESSAGE)]},
        config=config,
    )

    # Intent
    intent = state.get("intent")
    if intent:
        section("  Intent extracted", DIM)
        await p(0.4)
        bullet("action:    ", _c(intent.action, BOLD))
        bullet("domain:    ", _c(intent.domain, BOLD))
        bullet("confidence:", _c(f"{intent.confidence:.0%}", GREEN))
        bullet("ambiguous: ", str(intent.ambiguous))

    await p(1.0)

    # Plan
    section("  5-step network plan (DAG)", DIM)
    await print_plan(state)
    await p(1.5)

    # ====================================================================
    # PHASE 2  HITL Gate 1 — owner reviews the plan
    # ====================================================================
    pause_banner(1, "Owner reviews network topology")
    await p(0.6)
    out(f"\n{textwrap.indent(HITL_PLAN_REVIEW, '  ')}")
    await p(3.0)
    out(f"  {_c('→  Owner responds:', BOLD + YELLOW)} \"approve\"\n")
    await p(0.8)

    # Resume — validate_cot generates CoT trace then hits interrupt 2
    state = await graph.ainvoke(Command(resume="approve"), config=config)

    # Read CoT trace from the interrupt payload (node is suspended, not yet returned)
    cot_trace_for_display = state.get("cot_trace") or ""
    if not cot_trace_for_display:
        graph_state = graph.get_state(config)
        for task in graph_state.tasks:
            for intr in task.interrupts:
                payload = intr.value if hasattr(intr, "value") else {}
                if isinstance(payload, dict) and payload.get("cot_trace"):
                    cot_trace_for_display = payload["cot_trace"]
                    break

    # ====================================================================
    # PHASE 3  HITL Gate 2 — owner confirms chain-of-thought reasoning
    # ====================================================================
    pause_banner(2, "Owner confirms agent reasoning (CoT trace)")
    await p(0.6)
    out(f"\n  {_c('Claude Opus 4.6 walked the DAG and produced this reasoning trace:', DIM)}\n")
    await p(0.5)
    await print_cot_trace(cot_trace_for_display)
    await p(2.5)
    out(f"  {_c('→  Owner responds:', BOLD + YELLOW)} \"confirm\"")
    out(f"  {_c('   (No device is touched until the owner confirms)', DIM)}\n")
    await p(0.8)

    # ====================================================================
    # PHASE 4  Execution — parallel DAG fan-out via Send API
    # ====================================================================
    section("PHASE 4  Execution — DAG fan-out (Send API)")
    await p(0.6)
    out()
    await p(0.3)
    out(f"  {_c('Tick 1:', BOLD)} [create_payment_vlan] [create_guest_vlan]  "
        f"{_c('← parallel, no dependency', GREEN)}")
    await p(0.5)
    out(f"  {_c('Tick 2:', BOLD)} [configure_firewall]")
    await p(0.5)
    out(f"  {_c('Tick 3:', BOLD)} [setup_encryption]")
    await p(0.5)
    out(f"  {_c('Tick 4:', BOLD)} [apply_pci_compliance]")
    await p(0.5)
    out()

    state = await graph.ainvoke(Command(resume="confirm"), config=config)

    # ====================================================================
    # PHASE 5  Results
    # ====================================================================
    section("PHASE 5  Execution results")
    await print_execution_results(state)
    await p(1.0)

    # ====================================================================
    # PHASE 6  Final report
    # ====================================================================
    section("PHASE 6  Final report", GREEN)
    await p(0.5)
    report = state.get("report", "")
    if report:
        out()
        for line in report.splitlines():
            out(f"  {line}")

    plan = state.get("plan")
    if plan and plan.status.value == "COMPLETED":
        await p(1.0)
        out(f"\n  {_c('✓ Network configured. PCI-DSS compliant. Owner approved every step.', BOLD + GREEN)}")
        out(f"  {_c('  An SMB that couldn\'t afford a network engineer just got', DIM)}")
        out(f"  {_c('  enterprise-grade, PCI-DSS compliant infrastructure.', DIM)}\n")
    else:
        status = plan.status.value if plan else "UNKNOWN"
        out(f"\n  {_c(f'Plan status: {status}', YELLOW)}\n")

    await p(2.0)
    out(f"{_c('─' * 72, DIM)}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
