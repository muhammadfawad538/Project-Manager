# Line ending: LF
# Encoding: UTF-8

"""
MS Project XML export for pmagent.

Generates MS Project-compatible XML from WBS task data.
MS Project can open these files directly (.xml).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _parse_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MS Project date format YYYY-MM-DDTHH:MM:SS."""
    if not date_str or date_str in ("TBD", "N/A", ""):
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _hours_to_duration(hours: float) -> int:
    """Convert hours to MS Project duration in minutes."""
    return max(int(hours * 60), 1)


def export_msproject_xml(
    tasks: list[dict[str, Any]],
    project_name: str = "pmagent Project",
) -> str:
    """Generate MS Project-compatible XML from WBS task data.

    Args:
        tasks: list of task dicts with keys:
            id (str): task ID like "1.1"
            name (str): task name
            description (str): task description
            owner (str): assigned team member
            estimated_hours (float): effort in hours
            due_date (str): due date YYYY-MM-DD
            dependencies (list[str]): task IDs this task depends on
            priority (str): priority level
        project_name: name of the project

    Returns:
        MS Project XML string
    """
    # Build task lookup by ID
    task_map = {str(t["id"]): t for t in tasks}

    # Root UID for MS Project tasks (must start at 1, 0 is reserved for project summary)
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        "<Project>",
        f"  <Name>{_escape_xml(project_name)}</Name>",
        "  <Tasks>",
    ]

    uid = 1  # MS Project UID counter

    def _write_task(task: dict, uid: int) -> tuple[str, int]:
        """Write a single task XML block, including its outline children."""
        tid = str(task["id"])
        name = _escape_xml(task.get("name", "Unnamed Task"))
        desc = _escape_xml(task.get("description", ""))
        owner = _escape_xml(task.get("owner", ""))
        hours = float(task.get("estimated_hours", 0) or 0)
        due = _parse_date(task.get("due_date", ""))
        priority_map = {"must": 1, "should": 2, "nice-to-have": 3, "critical": 1, "high": 2, "medium": 3, "low": 4}
        priority = priority_map.get(task.get("priority", "").lower(), 3)
        duration = _hours_to_duration(hours)

        # Find outline level from task ID depth
        outline_level = len(tid.split("."))

        task_xml = [
            f'    <Task>',
            f'      <UID>{uid}</UID>',
            f'      <ID>{tid}</ID>',
            f'      <Name>{name}</Name>',
            f'      <Type>1</Type>',
            f'      <OutlineLevel>{outline_level}</OutlineLevel>',
            f'      <Duration>PT{duration}M</Duration>',
            f'      <Start>{due}</Start>',
            f'      <Finish>{due}</Finish>',
            f'      <Priority>{priority}</Priority>',
            f'      <ResourceNames>{owner}</ResourceNames>',
        ]
        if desc:
            task_xml.append(f'      <Notes>{desc}</Notes>')

        task_xml.append(f'    </Task>')
        return "\n".join(task_xml), uid + 1

    # Sort tasks by ID to maintain hierarchy
    sorted_tasks = sorted(tasks, key=lambda t: str(t["id"]))

    for task in sorted_tasks:
        task_xml, uid = _write_task(task, uid)
        xml_parts.append(task_xml)

    xml_parts.extend([
        "  </Tasks>",
        "</Project>",
    ])

    return "\n".join(xml_parts)


def export_wbs_csv(tasks: list[dict[str, Any]]) -> str:
    """Export WBS as a simple CSV file.

    Args:
        tasks: list of task dicts (same as export_msproject_xml)

    Returns:
        CSV string
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Task ID", "Task Name", "Description", "Owner",
        "Estimated Hours", "Due Date", "Dependencies", "Priority"
    ])

    for t in sorted(tasks, key=lambda x: str(x["id"])):
        writer.writerow([
            t.get("id", ""),
            t.get("name", ""),
            t.get("description", ""),
            t.get("owner", ""),
            t.get("estimated_hours", 0),
            t.get("due_date", ""),
            ";".join(t.get("dependencies", []) or []),
            t.get("priority", ""),
        ])

    return output.getvalue()
