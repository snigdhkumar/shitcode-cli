"""Skill creation, updating, and deletion manager for ShitCode.
"""

from __future__ import annotations

import json
from typing import Optional

from core.reporter import with_error_reporting
from tools.skills.catalog import ROOT_DIR, SKILLS_DIR, skills_list


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
