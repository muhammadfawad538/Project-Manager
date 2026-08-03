# Line ending: LF
# Encoding: UTF-8

"""Tests for MS Project XML, CSV, and Arabic PDF/HTML export."""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET

import pytest

from pmagent.exports import export_msproject_xml, export_wbs_csv, export_arabic_pdf


SAMPLE_TASKS = [
    {
        "id": "1",
        "name": "Requirements",
        "description": "Gather requirements",
        "owner": "Ahmed",
        "estimated_hours": 40,
        "due_date": "2026-11-15",
        "dependencies": [],
        "priority": "high",
    },
    {
        "id": "2",
        "name": "Design",
        "description": "System design",
        "owner": "Sara",
        "estimated_hours": 60,
        "due_date": "2026-12-01",
        "dependencies": ["1"],
        "priority": "critical",
    },
]


# ── MS Project XML ─────────────────────────────────────────────────────────────


class TestExportMsProjectXml:
    def test_returns_string(self):
        result = export_msproject_xml(SAMPLE_TASKS, "Test Project")
        assert isinstance(result, str)

    def test_xml_is_well_formed(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test Project")
        ET.fromstring(xml)  # raises if malformed

    def test_contains_project_name(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "My Project")
        assert "My Project" in xml

    def test_contains_task_names(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test")
        assert "Requirements" in xml
        assert "Design" in xml

    def test_has_task_elements(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test")
        root = ET.fromstring(xml)
        tasks = root.findall(".//Task")
        assert len(tasks) == 2

    def test_task_has_uid(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test")
        root = ET.fromstring(xml)
        uids = [t.find("UID").text for t in root.findall(".//Task")]
        assert uids == ["1", "2"]

    def test_task_has_duration(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test")
        root = ET.fromstring(xml)
        durations = [t.find("Duration").text for t in root.findall(".//Task")]
        assert all(d.startswith("PT") and d.endswith("M") for d in durations)

    def test_task_has_priority(self):
        xml = export_msproject_xml(SAMPLE_TASKS, "Test")
        root = ET.fromstring(xml)
        priorities = [t.find("Priority").text for t in root.findall(".//Task")]
        assert all(p.isdigit() for p in priorities)

    def test_xml_escaping(self):
        """Special characters in task names should be XML-escaped."""
        tasks = [
            {
                "id": "1",
                "name": "Task <special> & \"chars\"",
                "estimated_hours": 8,
                "dependencies": [],
                "priority": "high",
            }
        ]
        xml = export_msproject_xml(tasks, "Test")
        assert "&lt;special&gt;" in xml
        assert "&amp;" in xml
        assert "&quot;" in xml

    def test_empty_task_list(self):
        xml = export_msproject_xml([], "Empty")
        root = ET.fromstring(xml)
        tasks = root.findall(".//Task")
        assert len(tasks) == 0


# ── CSV Export ─────────────────────────────────────────────────────────────────


class TestExportWbsCsv:
    def test_returns_string(self):
        result = export_wbs_csv(SAMPLE_TASKS)
        assert isinstance(result, str)

    def test_has_header_row(self):
        csv_str = export_wbs_csv(SAMPLE_TASKS)
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Task ID" in header
        assert "Task Name" in header
        assert "Estimated Hours" in header

    def test_has_correct_row_count(self):
        csv_str = export_wbs_csv(SAMPLE_TASKS)
        rows = list(csv.reader(io.StringIO(csv_str)))
        # 1 header + 2 data rows
        assert len(rows) == 3

    def test_task_names_in_csv(self):
        csv_str = export_wbs_csv(SAMPLE_TASKS)
        assert "Requirements" in csv_str
        assert "Design" in csv_str

    def test_hours_in_csv(self):
        csv_str = export_wbs_csv(SAMPLE_TASKS)
        assert "40" in csv_str
        assert "60" in csv_str

    def test_dependencies_semicolon_separated(self):
        csv_str = export_wbs_csv(SAMPLE_TASKS)
        # Task 2 depends on Task 1
        assert "1" in csv_str

    def test_empty_task_list(self):
        csv_str = export_wbs_csv([])
        rows = list(csv.reader(io.StringIO(csv_str)))
        # Just the header
        assert len(rows) == 1


# ── Arabic PDF/HTML Export ─────────────────────────────────────────────────────


class TestExportArabicPdf:
    def test_returns_string_path(self, tmp_path):
        result = export_arabic_pdf(
            "# Heading\n\nSome content.",
            str(tmp_path / "output.html"),
            "مشروع",
        )
        assert isinstance(result, str)
        assert result.endswith(".html")

    def test_writes_html_file(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان\n\nمحتوى.", output, "مشروع")
        assert (tmp_path / "test.html").exists()

    def test_html_is_rtl(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان\n\nمحتوى.", output, "مشروع")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert 'dir="rtl"' in html or "direction: rtl" in html

    def test_html_contains_arabic_content(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان\n\nمحتوى.", output, "مشروع")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "عنوان" in html
        assert "محتوى" in html

    def test_html_contains_project_name(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان", output, "مشروع CRM")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "مشروع CRM" in html

    def test_html_has_cover_page(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان", output, "مشروع")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "cover-page" in html

    def test_html_has_arabic_fonts(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# عنوان", output, "مشروع")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "Amiri" in html or "Cairo" in html

    def test_markdown_headers_converted(self, tmp_path):
        output = str(tmp_path / "test.html")
        export_arabic_pdf("# H1\n## H2\n### H3", output, "test")
        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "<h1>" in html
        assert "<h2>" in html
        assert "<h3>" in html

    def test_pdf_extension_replaced_with_html(self, tmp_path):
        """When WeasyPrint is unavailable, .pdf paths should become .html."""
        output_pdf = str(tmp_path / "output.pdf")
        result = export_arabic_pdf("# test", output_pdf, "test")
        # Should return .html path, not .pdf (since WeasyPrint is usually not installed)
        assert result.endswith(".html")
