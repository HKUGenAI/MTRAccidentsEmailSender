"""Check that 'create safety awareness pulse' activates the runtime skill."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.skills import format_skills_for_prompt, load_skills, matching_skills  # noqa: E402


def main() -> None:
    skills = load_skills()
    names = {s.name for s in skills}
    assert "safety-awareness-pulse" in names, names

    matched = matching_skills("please create safety awareness pulse for depot staff")
    assert [s.name for s in matched] == ["safety-awareness-pulse"], [s.name for s in matched]
    assert not matching_skills("email me the latest restaurant inspections")

    block = format_skills_for_prompt("create safety awareness pulse")
    assert "Available skills" in block
    assert "safety-awareness-pulse" in block
    assert "Active skill(s)" in block
    assert "SAFETY AWARENESS PULSE" in block
    assert "extract_rows" in block
    print("skills OK:", [s.name for s in skills])
    print("matched 'create safety awareness pulse' ->", [s.name for s in matched])


if __name__ == "__main__":
    main()
