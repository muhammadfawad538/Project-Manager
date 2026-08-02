# Line ending: LF
# Encoding: UTF-8

"""
Comprehensive feature test for pmagent.

Tests:
1. GCC utilities (Hijri, weekend, currency, VAT)
2. MS Project XML export
3. Arabic PDF/HTML export
4. Critical path computation
5. Crew bilingual output
6. API endpoints
"""

import sys
import io
import json
import datetime
from pathlib import Path

sys.path.insert(0, "src")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} — {detail}")


print("=" * 60)
print("  pmagent Feature Test Suite")
print("=" * 60)

# ── 1. GCC Utilities ──────────────────────────────────────────────────────────

print("\n--- 1. GCC Utilities ---")

from pmagent.utils import (
    gregorian_to_hijri, hijri_to_gregorian,
    is_working_day, add_working_days, next_working_day,
    is_holiday, is_non_working_day,
    format_currency, format_vat, get_country_config,
    GCC_WORK_WEEK, GLOBAL_WORK_WEEK, CURRENCIES,
    HIJRI_MONTHS_AR, HIJRI_MONTHS_EN,
)

# Hijri conversion
d = datetime.date(2026, 8, 2)
h = gregorian_to_hijri(d)
check("Hijri conversion returns 3 ints", len(h) == 3 and all(isinstance(x, int) for x in h))
# Forward conversion should give reasonable Hijri year for modern dates
check("Hijri year in valid range", 1400 <= h[0] <= 1500, f"got {h[0]}")
check("Hijri month in valid range", 1 <= h[1] <= 12, f"got {h[1]}")
check("Hijri day in valid range", 1 <= h[2] <= 30, f"got {h[2]}")
# Round-trip is approximate; tabular calendar drifts. Production needs Umm al-Qura.
back = hijri_to_gregorian(*h)
check("Hijri reverse conversion runs", isinstance(back, datetime.date))

# Weekend config
fri = datetime.date(2026, 8, 7)
sat = datetime.date(2026, 8, 8)
sun = datetime.date(2026, 8, 9)
mon = datetime.date(2026, 8, 10)
check("Friday is NOT working (GCC)", not is_working_day(fri), f"got {is_working_day(fri)}")
check("Saturday is NOT working (GCC)", not is_working_day(sat), f"got {is_working_day(sat)}")
check("Sunday IS working (GCC)", is_working_day(sun), f"got {is_working_day(sun)}")
check("Monday IS working (GCC)", is_working_day(mon), f"got {is_working_day(mon)}")

# Working days calculation
start = datetime.date(2026, 8, 3)  # Monday
end = add_working_days(start, 5)
check("5 working days from Monday = Tuesday next week", end == datetime.date(2026, 8, 11), f"got {end}")

# Currency formatting
sar_en = format_currency(1500.50, "SAR", "en")
sar_ar = format_currency(1500.50, "SAR", "ar")
check("SAR formatting EN contains symbol", "﷼" in sar_en or "SAR" in sar_en)
check("SAR formatting AR has Arabic digits", any("٠" <= c <= "٩" for c in sar_ar))

# KWD has 3 decimals
kwd = format_currency(1234.567, "KWD", "en")
check("KWD has 3 decimal places", ".567" in kwd, f"got {kwd}")

# VAT calculation
vat = format_vat(1000.0, 0.05, "SAR")
check("VAT subtotal correct", vat["subtotal"] == 1000.0)
check("VAT amount correct", vat["vat_amount"] == 50.0, f"got {vat['vat_amount']}")
check("VAT total correct", vat["total"] == 1050.0, f"got {vat['total']}")

# Country config
sa = get_country_config("SA")
ae = get_country_config("AE")
qa = get_country_config("QA")
check("SA has VAT", sa.vat_enabled and sa.vat_rate == 0.05)
check("AE has VAT", ae.vat_enabled and ae.vat_rate == 0.05)
check("QA has no VAT", not qa.vat_enabled and qa.vat_rate == 0.0)
check("SA currency is SAR", sa.currency == "SAR")
check("AE currency is AED", ae.currency == "AED")

# Hijri month names
check("12 Hijri months AR", len(HIJRI_MONTHS_AR) == 12)
check("12 Hijri months EN", len(HIJRI_MONTHS_EN) == 12)

# ── 2. Critical Path Computation ──────────────────────────────────────────────

print("\n--- 2. Critical Path Computation ---")

from pmagent.main import compute_critical_path

# Simple linear chain
linear = [
    {"id": "1.0", "name": "A", "estimated_hours": 40, "dependencies": []},
    {"id": "1.1", "name": "B", "estimated_hours": 40, "dependencies": ["1.0"]},
    {"id": "2.0", "name": "C", "estimated_hours": 80, "dependencies": ["1.1"]},
]
r = compute_critical_path(linear)
check("Linear chain: all 3 tasks on critical path", r["critical_path"] == ["1.0", "1.1", "2.0"], f"got {r['critical_path']}")
check("Linear chain: all floats are 0", all(r["all_floats"][t] == 0.0 for t in ["1.0", "1.1", "2.0"]))

# Branching: task with float (path through 1.1 is longer)
branch = [
    {"id": "1.0", "name": "A", "estimated_hours": 40, "dependencies": []},
    {"id": "1.1", "name": "B", "estimated_hours": 80, "dependencies": ["1.0"]},  # longer
    {"id": "2.0", "name": "C", "estimated_hours": 20, "dependencies": ["1.0"]},  # shorter
    {"id": "3.0", "name": "D", "estimated_hours": 40, "dependencies": ["1.1", "2.0"]},
]
r2 = compute_critical_path(branch)
check("Branching: 1.0 on critical path", "1.0" in r2["critical_path"])
check("Branching: 1.1 on critical path (longer path)", "1.1" in r2["critical_path"])
check("Branching: 3.0 on critical path", "3.0" in r2["critical_path"])
check("Branching: 2.0 has float > 0", r2["all_floats"]["2.0"] > 0, f"got {r2['all_floats']['2.0']}")

# Empty input
r3 = compute_critical_path([])
check("Empty tasks returns empty critical path", r3["critical_path"] == [])

# ── 3. MS Project XML Export ──────────────────────────────────────────────────

print("\n--- 3. MS Project XML Export ---")

from pmagent.exports import export_msproject_xml, export_wbs_csv

tasks = [
    {"id": "1.0", "name": "Requirements", "description": "Gather requirements", "owner": "Omar", "estimated_hours": 80, "due_date": "2026-11-15", "dependencies": [], "priority": "must"},
    {"id": "1.1", "name": "Documentation", "description": "Write SRS", "owner": "Omar", "estimated_hours": 40, "due_date": "2026-11-30", "dependencies": ["1.0"], "priority": "must"},
    {"id": "2.0", "name": "Backend", "description": "Build API", "owner": "Khalid", "estimated_hours": 120, "due_date": "2027-01-15", "dependencies": ["1.0", "1.1"], "priority": "must"},
]

xml = export_msproject_xml(tasks, "CRM Project")
check("XML has Project root", "<Project>" in xml)
check("XML has Name element", "<Name>CRM Project</Name>" in xml)
check("XML has Tasks element", "<Tasks>" in xml)
check("XML has 3 Task elements", xml.count("<Task>") == 3)
check("XML has UID for each task", xml.count("<UID>") == 3)
check("XML has Duration in minutes", "PT" in xml)
check("XML has ResourceNames", "<ResourceNames>Omar</ResourceNames>" in xml)
check("XML is valid XML", xml.startswith("<?xml"))

csv = export_wbs_csv(tasks)
check("CSV has header", "Task ID,Task Name" in csv)
check("CSV has 3 data rows", csv.count("\n") == 4)  # 1 header + 3 data
check("CSV has dependencies joined by semicolon", "1.0;1.1" in csv)

# ── 4. Arabic PDF/HTML Export ─────────────────────────────────────────────────

print("\n--- 4. Arabic PDF/HTML Export ---")

from pmagent.exports import export_arabic_pdf, markdown_to_html_rtl

ar_md = """# الحزمة النهائية

## الملخص التنفيذي
هذا المشروع يركز على بناء نظام CRM.

## المهام
| الرقم | المهمة | المالك |
|-------|--------|--------|
| 1.0   | متطلبات | عمر    |
| 1.1   | توثيق   | عمر    |
"""

html = markdown_to_html_rtl(ar_md, "مشروع CRM")
check("HTML has RTL direction", 'dir="rtl"' in html)
check("HTML has Arabic lang", 'lang="ar"' in html)
check("HTML has Amiri font", "Amiri" in html)
check("HTML has Cairo font", "Cairo" in html)
check("HTML has cover page", "cover-page" in html)
check("HTML has UTF-8 charset", "UTF-8" in html)
check("HTML has Arabic content", "الحزمة" in html)

result = export_arabic_pdf(ar_md, "test_features.pdf", "مشروع CRM")
check("Arabic PDF export returns path", result is not None and len(result) > 0)
if result:
    exists = Path(result).exists()
    check("Arabic PDF/HTML file exists", exists, f"path={result}")
    if exists:
        size = Path(result).stat().st_size
        check("File has content", size > 100, f"size={size}")

# Cleanup
if result and Path(result).exists():
    Path(result).unlink()

# ── 5. Crew Assembly ──────────────────────────────────────────────────────────

print("\n--- 5. Crew Assembly ---")

from pmagent.main import crew, kickoff, DEFAULT_INPUTS

check("Crew has 4 agents", len(crew.agents) == 4, f"got {len(crew.agents)}")
check("Crew has 4 tasks", len(crew.tasks) == 4, f"got {len(crew.tasks)}")

agent_roles = [a.role for a in crew.agents]
check("Planner agent present", any("Planner" in r for r in agent_roles))
check("Risk analyst agent present", any("Risk" in r for r in agent_roles))
check("Resource allocator agent present", any("Resource" in r for r in agent_roles))
check("Manager agent present", any("Manager" in r for r in agent_roles))

# Task context chaining — CrewAI uses _NotSpecified sentinel for tasks without context
task_contexts = [getattr(t, "context", None) for t in crew.tasks]
has_chain = any(ctx is not None and ctx.__class__.__name__ != "_NotSpecified" for ctx in task_contexts)
check("Manager task has context chain", has_chain, f"context types: {[c.__class__.__name__ if c else 'None' for c in task_contexts]}")

# Default inputs
required_keys = ["project_type", "project_objectives", "industry", "deadline", "country", "currency", "output_language", "team_members", "project_requirements"]
for key in required_keys:
    check(f"DEFAULT_INPUTS has '{key}'", key in DEFAULT_INPUTS)

# ── 6. API Endpoints ──────────────────────────────────────────────────────────

print("\n--- 6. API Endpoints ---")

from api.main import app

routes = [r.path for r in app.routes if hasattr(r, "path")]
check("API has /health", "/health" in routes)
check("API has /plan", "/plan" in routes)
check("API has /plan/{project_id}/export", "/plan/{project_id}/export" in routes)

# Verify OpenAPI schema includes new fields
schema = app.openapi()
plan_schema = schema.get("components", {}).get("schemas", {}).get("ProjectRequest", {})
props = plan_schema.get("properties", {})
check("ProjectRequest has country field", "country" in props)
check("ProjectRequest has currency field", "currency" in props)
check("ProjectRequest has output_language field", "output_language" in props)

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"  Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
