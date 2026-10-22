"""Load markdown skills and expose each one as a tool the model can choose to call.

Skills live in agent/skills/<name>/SKILL.md. Calling a skill tool returns the
playbook; the model then follows it with the other tools (search, DB, email).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None

    @property
    def tool_name(self) -> str:
        return "use_" + self.name.replace("-", "_")


def _parse_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        return {}, raw
    fm_block = rest[:end].strip()
    body = rest[end + 4 :].lstrip("\n")
    meta: dict[str, object] = {}
    current_list: str | None = None
    items: list[str] = []
    for line in fm_block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            if current_list:
                meta[current_list] = items
                items = []
            key = stripped[:-1].strip()
            current_list = key
            meta[key] = []
            continue
        if stripped.startswith("- ") and current_list:
            items.append(stripped[2:].strip().strip("\"'"))
            continue
        current_list = None
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            meta[key.strip()] = val.strip().strip("\"'")
    if current_list:
        meta[current_list] = items
    return meta, body


def load_skills(directory: Path | None = None) -> list[Skill]:
    root = directory or SKILLS_DIR
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for path in sorted(root.glob("*/SKILL.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        name = str(meta.get("name") or path.parent.name)
        desc = str(meta.get("description") or "")
        triggers = meta.get("triggers") or []
        if not isinstance(triggers, list):
            triggers = [str(triggers)]
        skills.append(
            Skill(
                name=name,
                description=desc,
                triggers=[str(t) for t in triggers],
                body=body.strip(),
                path=path,
            )
        )
    return skills


def _hong_kong_today() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
    return (
        f"Hong Kong today: {today.isoformat()} "
        f"(month_day {today.strftime('%m-%d')}, timezone Asia/Hong_Kong)."
    )


def format_skill_playbook(skill: Skill) -> str:
    examples = ", ".join(skill.triggers) if skill.triggers else skill.name
    return "\n\n".join(
        [
            f"Skill loaded: {skill.name}",
            _hong_kong_today(),
            "Reply in the same language as the user's request "
            "(Traditional Chinese if they wrote in Chinese, English if they wrote in English, "
            "and so on). If the message mixes languages, use the language of the actual ask. "
            "Do not default to Chinese or English unless the query does.",
            f"When to use this skill (examples): {examples}",
            "Follow the playbook below using the other bound tools. Stop at the first usable hit.",
            skill.body,
        ]
    )


def _skill_to_tool(skill: Skill) -> StructuredTool:
    def _run() -> str:
        return format_skill_playbook(skill)

    examples = ", ".join(skill.triggers[:6]) if skill.triggers else skill.name
    description = (
        f"{skill.description or skill.name} "
        "This is a skill: a multi-step playbook, not a data lookup. "
        f"Call this tool only when the user actually wants that task (examples: {examples}). "
        "It returns the full instructions; then use search / database / email tools as directed. "
        "Do not call it for unrelated news search or email requests."
    )
    return StructuredTool.from_function(
        name=skill.tool_name,
        description=description,
        func=_run,
    )


def build_skill_tools(directory: Path | None = None) -> list[BaseTool]:
    """One LangChain tool per SKILL.md so the model can choose to load a playbook."""
    return [_skill_to_tool(skill) for skill in load_skills(directory)]
