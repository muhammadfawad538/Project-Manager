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
    "project_type": "Residential Villa Construction – 20-Marla Plot",
    "project_objectives": "Complete construction of a 2-story villa on a 20-marla plot within 3 months, including foundation, structure, MEP, and finishing",
    "industry": "Construction",
    "deadline": "3 months",
    "country": "Saudi Arabia",
    "currency": "SAR",
    "team_members": """
- Ali (Site Engineer)
- Ahmed (Carpenter / Steel Worker)
- Usman (Electrician)
- Hassan (Plumber)
- Bilal (General Laborer)
""",
    "project_requirements": """
- Excavation and foundation work
- Column and beam reinforcement and casting
- Brick masonry and wall construction
- Roof slab casting
- Electrical wiring and conduit installation
- Plumbing pipework and drainage
- Window and door frame installation
- Interior and exterior plastering
- Flooring (marble/tiles)
- Paint and finishing
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
    ar_inputs["project_type"] = "بناء فيلا سكنية - قطعة 20 مارلا"
    ar_inputs["project_objectives"] = "إكمال بناء فيلا من طابقين على قطعة 20 مارلا خلال 3 أشهر"
    ar_inputs["industry"] = "الإنشاءات"
    ar_inputs["deadline"] = "3 أشهر"
    ar_inputs["country"] = "المملكة العربية السعودية"
    ar_inputs["currency"] = "SAR"
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
