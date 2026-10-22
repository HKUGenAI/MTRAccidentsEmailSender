"""Load markdown skills and inject matching ones into the agent system prompt.

Skills live in agent/skills/<name>/SKILL.md (runtime). Cursor copies may also
exist under .cursor/skills/; those are for the IDE, not this loader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None

    def matches(self, text: str) -> bool:
        hay = (text or "").lower()
        if not hay:
            return False
        if self.name.replace("-", " ") in hay:
            return True
        return any(t.lower() in hay for t in self.triggers if t.strip())


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


def matching_skills(user_request: str, skills: list[Skill] | None = None) -> list[Skill]:
    loaded = skills if skills is not None else load_skills()
    return [s for s in loaded if s.matches(user_request)]


def format_skills_for_prompt(user_request: str, skills: list[Skill] | None = None) -> str:
    loaded = skills if skills is not None else load_skills()
    if not loaded:
        return ""
    catalog = "\n".join(
        f"- {s.name}: {s.description or 'see SKILL.md'}" for s in loaded
    )
    matched = matching_skills(user_request, loaded)
    parts = [
        "Available skills (follow a skill when the user request matches it):",
        catalog,
    ]
    if matched:
        parts.append("Active skill(s) for this request — follow them now:")
        for s in matched:
            parts.append(f"### {s.name}\n{s.body}")
    return "\n\n".join(parts)
