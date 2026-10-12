"""Self-improving skills system for MCP_NEW.
Scans and manages clean custom developer skills inside ./skills/ with zero Hermes bloat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.reporter import with_error_reporting

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter between --- fences."""
    meta = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_fm = parts[1]
            for line in raw_fm.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta


@with_error_reporting("skills_list")
def skills_list(category: Optional[str] = None) -> str:
    """List available custom procedures and workflow guides in the skills directory.

    Args:
        category: Optional category filter.
    """
    skills = []

    for skill_file in SKILLS_DIR.glob("**/SKILL.md"):
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(content)
            skill_name = meta.get("name") or skill_file.parent.name
            skill_cat = meta.get("category") or skill_file.parent.parent.name
            if skill_cat == "skills":
                skill_cat = "custom"

            if category and skill_cat != category:
                continue

            desc = meta.get("description", "")
            if not desc:
                # Find first heading or non-empty line after frontmatter
                for line in content.splitlines():
                    if line.startswith("# "):
                        desc = line[2:].strip()
                        break

            skills.append({
                "name": skill_name,
                "category": skill_cat,
                "description": desc or "Custom skill procedure",
                "path": str(skill_file.relative_to(ROOT_DIR)).replace("\\", "/"),
            })
        except Exception:
            continue

    data = {
        "skills": skills,
        "total_available": len(skills),
        "skills_directory": str(SKILLS_DIR).replace("\\", "/"),
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


@with_error_reporting("skill_view")
def skill_view(name: str) -> str:
    """View the full markdown instructions, workflows, and prompt guidelines for a specific skill.

    Args:
        name: Name of the skill to inspect and load into context.
    """
    # 1. Direct path check
    for skill_path in SKILLS_DIR.glob(f"**/{name}/SKILL.md"):
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8", errors="replace")

    # 2. Check by frontmatter name
    for skill_path in SKILLS_DIR.glob("**/SKILL.md"):
        try:
            content = skill_path.read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(content)
            if meta.get("name") == name:
                return content
        except Exception:
            pass

    return f"Error: Skill '{name}' not found in {SKILLS_DIR}."


@with_error_reporting("skill_manage")
def skill_manage(
    action: str,
    name: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """Create, update, or delete a skill inside ./skills/.

    Args:
        action: Management action: 'create', 'update', 'delete', or 'list'.
        name: Name of the skill (required for create/update/delete).
        content: Markdown instructions for the skill (for 'create' or 'update').
        category: Optional category folder name (default 'custom').
    """
    category = category or "custom"

    if action == "list":
        return skills_list(category=category)

    if not name:
        return "Error: 'name' is required for skill management actions (create, update, delete)."

    target_dir = SKILLS_DIR / category / name
    target_file = target_dir / "SKILL.md"

    if action == "create":
        target_dir.mkdir(parents=True, exist_ok=True)
        if not content:
            content = (
                f"---\nname: {name}\ncategory: {category}\ndescription: Custom workflow for {name}\n---\n\n"
                f"# {name}\n\n1. Step 1\n2. Step 2\n"
            )
        target_file.write_text(content, encoding="utf-8")
        return json.dumps({
            "status": "created",
            "name": name,
            "category": category,
            "path": str(target_file.relative_to(ROOT_DIR)).replace("\\", "/"),
        })

    elif action == "update":
        if not target_file.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content or "", encoding="utf-8")
        return json.dumps({
            "status": "updated",
            "name": name,
            "path": str(target_file.relative_to(ROOT_DIR)).replace("\\", "/"),
        })

    elif action == "delete":
        if target_file.exists():
            target_file.unlink()
            try:
                target_dir.rmdir()
            except Exception:
                pass
            return json.dumps({"status": "deleted", "name": name})
        return json.dumps({"status": "not_found", "name": name})

    return f"Unknown action: '{action}'. Available: create, update, delete."
