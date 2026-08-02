# Line ending: LF
# Encoding: UTF-8

"""
Bilingual test runner for pmagent.

Run both English and Arabic and compare side-by-side.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, "src")

from pmagent.main import kickoff

BASE_INPUTS = {
    "project_type": "Enterprise CRM System Implementation",
    "project_objectives": "Implement a customer relationship management (CRM) system for 500+ users across 3 departments within 6 months",
    "industry": "Technology / Software",
    "deadline": "6 months",
    "team_members": """
- Sara (Project Manager)
- Khalid (Backend Developer)
- Noura (Frontend Developer)
- Faisal (QA Engineer)
- Laila (DevOps Engineer)
- Omar (Business Analyst)
""",
    "project_requirements": """
- Requirements gathering and stakeholder interviews
- Backend API development (RESTful services)
- Frontend UI development (React-based dashboard)
- Database design and migration
- User authentication and role-based access control
- Integration with existing ERP and email systems
- Automated testing and CI/CD pipeline setup
- User training and documentation
- Phased rollout to 3 departments
- Post-launch support and bug fixing
""",
}


def run_test(language: str, inputs: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"  Running: {language}")
    print(f"{'='*60}\n")

    inputs["output_language"] = language
    result = kickoff(inputs=inputs)

    # Save raw output to file
    out_dir = Path("test_outputs")
    out_dir.mkdir(exist_ok=True)

    raw_path = out_dir / f"output_{language.lower()}.md"
    raw_path.write_text(result["raw_output"], encoding="utf-8")

    json_path = out_dir / f"output_{language.lower()}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nSaved: {raw_path}")
    print(f"Saved: {json_path}")

    return result


def compare_outputs() -> None:
    en_file = Path("test_outputs/output_english.md")
    ar_file = Path("test_outputs/output_arabic.md")

    if not en_file.exists() or not ar_file.exists():
        print("Run both tests first.")
        return

    en = en_file.read_text(encoding="utf-8")
    ar = ar_file.read_text(encoding="utf-8")

    print(f"\n{'='*60}")
    print("  Comparison")
    print(f"{'='*60}")
    print(f"English output: {len(en)} chars, {en.count(chr(10))} lines")
    print(f"Arabic output:  {len(ar)} chars, {ar.count(chr(10))} lines")

    # Check for Arabic script in Arabic output
    arabic_chars = sum(1 for c in ar if "؀" <= c <= "ۿ")
    print(f"Arabic chars in Arabic output: {arabic_chars}")

    # Check that English output has no Arabic script
    arabic_in_en = sum(1 for c in en if "؀" <= c <= "ۿ")
    print(f"Arabic chars in English output: {arabic_in_en}")


if __name__ == "__main__":
    # Run English
    en_result = run_test("English", BASE_INPUTS.copy())

    # Run Arabic
    ar_inputs = BASE_INPUTS.copy()
    ar_inputs["project_type"] = "تنفيذ نظام إدارة علاقات العملاء (CRM)"
    ar_inputs["project_objectives"] = "تنفيذ نظام إدارة علاقات العملاء لـ 500+ مستخدم عبر 3 أقسام خلال 6 أشهر"
    ar_inputs["industry"] = "التكنولوجيا / البرمجيات"
    ar_inputs["deadline"] = "6 أشهر"
    ar_inputs["team_members"] = """
- سارة (مديرة المشروع)
- خالد (مطور خلفي)
- نورة (مطورة واجهات أمامية)
- فيصل (مهندس ضمان جودة)
- ليلى (مهندسة DevOps)
- عمر (محلل أعمال)
"""
    ar_inputs["project_requirements"] = """
- جمع المتطلبات ومقابلات أصحاب المصلحة
- تطوير واجهة برمجة التطبيقات الخلفية (RESTful)
- تطوير الواجهة الأمامية (لوحة تحكم React)
- تصميم قاعدة البيانات والترحيل
- مصادقة المستخدم والتحكم في الأدوار
- التكامل مع أنظمة ERP والبريد الإلكتروني الحالية
- إعداد الاختبارات الآلية وخط أنابيب CI/CD
- تدريب المستخدمين والتوثيق
- الإطلاق التدريجي عبر 3 أقسام
- دعم ما بعد الإطلاق وإصلاح الأخطاء
"""
    ar_result = run_test("Arabic", ar_inputs)

    # Compare
    compare_outputs()

    print(f"\nEnglish cost: ${en_result.get('cost_usd', 'N/A')}")
    print(f"Arabic cost:  ${ar_result.get('cost_usd', 'N/A')}")
