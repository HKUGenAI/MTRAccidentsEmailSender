"""Check that skills load as tools the model can choose to call."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.skills import build_skill_tools, format_skill_playbook, load_skills  # noqa: E402


def main() -> None:
    skills = load_skills()
    names = {s.name for s in skills}
    assert "safety-awareness-pulse" in names, names
    pulse = next(s for s in skills if s.name == "safety-awareness-pulse")
    assert pulse.tool_name == "use_safety_awareness_pulse"

    tools = build_skill_tools()
    tool_names = [t.name for t in tools]
    assert "use_safety_awareness_pulse" in tool_names, tool_names
    skill_tool = next(t for t in tools if t.name == "use_safety_awareness_pulse")
    assert "safety awareness pulse" in (skill_tool.description or "").lower()

    playbook = skill_tool.invoke({})
    assert "Skill loaded: safety-awareness-pulse" in playbook
    assert "Hong Kong today:" in playbook
    assert "same language as the user" in playbook.lower() or "same language as the user's request" in playbook
    assert "labour.gov.hk" in playbook
    assert "extract_rows" in playbook
    assert "web_search" in playbook
    assert "send_email" in playbook
    assert format_skill_playbook(pulse).startswith("Skill loaded:")

    print("skills OK:", [s.name for s in skills])
    print("skill tools:", tool_names)


if __name__ == "__main__":
    main()
