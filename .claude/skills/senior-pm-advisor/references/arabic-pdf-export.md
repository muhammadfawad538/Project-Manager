# Line ending: LF
# Encoding: UTF-8

# Arabic PDF Export Guide

GCC government and enterprise procurement requires deliverables in Arabic
as formal PDF documents. This guide covers the requirements and approach
for generating compliant Arabic PDFs from pmagent output.

---

## GCC Document Requirements

### Saudi Arabia (NCA / Etimad)
- All tender documents must be in Arabic
- Document must include: document ID, issue date, revision number
- Signatures and stamps required on final pages
- Paper size: A4

### UAE (TDRA / Tawteen)
- Bilingual documents accepted, but Arabic version is primary
- Must include: project number, entity logo, confidentiality notice
- Paper size: A4

### Qatar (Ashghal / Kahramaa)
- Arabic only for government tenders
- Must include: project reference, QCS compliance notice
- Paper size: A4

---

## RTL Layout Considerations

### Text Direction
- Arabic is right-to-left (RTL). All body text, headings, and table
  content must flow RTL.
- Numbers in tables: use Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) or Western
  digits (0123456789) consistently. GCC government forms typically
  use Western digits in financial tables and Arabic-Indic in narrative text.

### Tables in RTL
- Column order: reverse for RTL (first column becomes rightmost)
- Alignment: right-align all Arabic text
- Header row: bold, with a bottom border
- Page breaks: avoid splitting a table row across pages

### Page Margins
- Standard: 2.5cm all sides
- Header: entity name (Arabic + English), document title, date
- Footer: page number in Arabic (صفحة X من Y), confidentiality notice

---

## Font Requirements

### Arabic-Safe Fonts (no ligature issues)
| Font | License | Notes |
|------|---------|-------|
| `Amiri` | OFL | Traditional Naskh style — preferred for formal docs |
| `Noto Naskh Arabic` | OFL | Clean, modern — good for tables |
| `Cairo` | OFL | Contemporary — good for headings |
| `Tajawal` | OFL | Modern, readable at small sizes |

### Minimum Font Sizes
- Body text: 11pt
- Table text: 9pt
- Headings: 14pt (H1), 12pt (H2), 11pt (H3)
- Footer: 8pt

---

## Document Structure (Arabic PDF)

```
صفحة العنوان (Cover Page)
├── اسم المشروع (Project Name)
├── رقم المستند (Document ID)
├── التاريخ (Date)
├── الجهة المالكة (Client Entity)
├── الشركة المنفذة (Contractor)
└── الختم والتوقيع (Signature & Stamp)

الملخص التنفيذي (Executive Summary)
├── نظرة عامة (Overview)
├── الأهداف (Objectives)
└── النتائج المتوقعة (Expected Outcomes)

خطة المشروع (Project Plan)
├── الأهداف (Goals)
├── نطاق العمل (Scope)
├── هيكل تقسيم العمل (WBS)
│   └── جدول المهام (Task Table)
├── المعالم (Milestones)
├── الجدول الزمني (Timeline)
├── المسار الحرج (Critical Path)
└── الافتراضات (Assumptions)

سجل المخاطر (Risk Register)
├── ملخص المخاطر (Risk Summary Table)
├── التفاصيل (Detailed Entries)
└── معايير التصعيد (Escalation Criteria)

توزيع الموارد (Resource Allocation)
├── مصفوفة التوزيع (Allocation Matrix)
├── تحليل العبء (Load Analysis)
└── خيارات إعادة التوازن (Rebalancing Plan)

خطة الاتصالات (Communication Plan)

الخطوات التالية (Next Steps)

تقييم مدير المشروع (PM Assessment)
├── الحالة العامة (Overall Health)
├── أهم 3 مخاطر (Top 3 Risks)
└── التوصية (Recommendation)
```

---

## Technical Approach

### Option A: Markdown → WeasyPrint (recommended)
```python
from weasyprint import HTML, CSS
html = markdown_to_html(arabic_markdown, rtl=True)
pdf = HTML(string=html).write_pdf(
    stylesheets=[CSS(string='@page { size: A4; margin: 2.5cm; direction: rtl; }')]
)
```

### Option B: Markdown → ReportLab (more control)
```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
# Manual layout for precise control over RTL tables
```

### Option C: Use a pre-built Arabic PDF service
- For production: integrate with a service that handles RTL PDF natively
- Ensures compliance with government formatting standards

---

## Compliance Checklist

Before sending any Arabic PDF to a GCC client, verify:

- [ ] All headings are in Arabic
- [ ] All table column headers are in Arabic
- [ ] Numbers use consistent digit format (Western or Arabic-Indic)
- [ ] Document has a cover page with entity names in Arabic
- [ ] Page numbers are in Arabic (صفحة X من Y)
- [ ] Footer has confidentiality notice in Arabic
- [ ] Signatures section included (if formal deliverable)
- [ ] Paper size is A4
- [ ] Margins are 2.5cm all sides
- [ ] Font is Arabic-safe (Amiri, Cairo, or Noto Naskh Arabic)
- [ ] RTL text direction applied throughout
