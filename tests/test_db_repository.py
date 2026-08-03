# Line ending: LF
# Encoding: UTF-8

"""Tests for the database repository layer — projects, tasks, issues, change requests, milestones, daily logs."""

from __future__ import annotations

import datetime

import pytest

from pmagent.db.models import (
    ProjectStatus, TaskStatus, MilestoneStatus, IssueStatus,
    IssuePriority, ChangeRequestStatus, Priority,
)
from pmagent.db.repository import (
    create_project, get_project, list_projects, update_project_status,
    add_team_member, get_team_members,
    create_task, get_task, get_project_tasks, update_task_status,
    update_task_progress, reassign_task, find_blockers,
    create_milestone, get_project_milestones, update_milestone_status,
    create_daily_log, get_project_daily_logs,
    save_sprint_report, get_sprint_reports,
    create_issue, get_project_issues, get_issue,
    update_issue_status, assign_issue,
    create_change_request, get_project_change_requests, get_change_request,
    update_change_request_status,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_project(db):
    """Create a project using the test session and return its id."""
    p = create_project(db, name="Test Project", project_type="IT", industry="Tech")
    db.flush()
    return p.id


def _make_member(db, project_id):
    """Create a team member and return its id."""
    m = add_team_member(db, project_id=project_id, name="Ahmed", role="Dev")
    db.flush()
    return m.id


# ── Projects ───────────────────────────────────────────────────────────────────


class TestProjects:
    def test_create_project(self, db):
        p = create_project(db, name="CRM", project_type="IT", industry="Tech")
        db.flush()
        assert p.id is not None
        assert p.name == "CRM"
        assert p.status == ProjectStatus.active

    def test_get_project(self, db):
        pid = _make_project(db)
        fetched = get_project(db, pid)
        assert fetched is not None
        assert fetched.name == "Test Project"

    def test_get_nonexistent_project(self, db):
        fetched = get_project(db, 99999)
        assert fetched is None

    def test_list_projects(self, db):
        _make_project(db)
        _make_project(db)
        projects = list_projects(db)
        assert len(projects) == 2

    def test_list_projects_filter_by_status(self, db):
        _make_project(db)
        p2 = create_project(db, name="Old", project_type="IT")
        db.flush()
        pid2 = p2.id
        update_project_status(db, pid2, ProjectStatus.archived)
        active = list_projects(db, status=ProjectStatus.active)
        archived = list_projects(db, status=ProjectStatus.archived)
        assert len(active) == 1
        assert len(archived) == 1


# ── Team Members ───────────────────────────────────────────────────────────────


class TestTeamMembers:
    def test_add_member(self, db):
        pid = _make_project(db)
        m = add_team_member(db, project_id=pid, name="Sara", role="PM")
        db.flush()
        assert m.id is not None
        assert m.name == "Sara"

    def test_get_team_members(self, db):
        pid = _make_project(db)
        add_team_member(db, project_id=pid, name="A", role="Dev")
        add_team_member(db, project_id=pid, name="B", role="Designer")
        members = get_team_members(db, pid)
        assert len(members) == 2


# ── Tasks ──────────────────────────────────────────────────────────────────────


class TestTasks:
    def test_create_task(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Build API", estimated_hours=40, priority="high")
        db.flush()
        assert t.id is not None
        assert t.status == TaskStatus.todo
        assert t.progress_pct == 0.0

    def test_default_task_status_is_todo(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        assert t.status == TaskStatus.todo

    def test_update_task_status(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        tid = t.id
        update_task_status(db, tid, TaskStatus.in_progress)
        fetched = get_task(db, tid)
        assert fetched.status == TaskStatus.in_progress

    def test_update_task_progress_clamped(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        update_task_progress(db, t.id, 150.0)
        fetched = get_task(db, t.id)
        assert fetched.progress_pct == 100.0

    def test_update_task_progress_negative_clamped(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        update_task_progress(db, t.id, -10.0)
        fetched = get_task(db, t.id)
        assert fetched.progress_pct == 0.0

    def test_reassign_task(self, db):
        pid = _make_project(db)
        m1 = add_team_member(db, project_id=pid, name="A", role="Dev")
        m2 = add_team_member(db, project_id=pid, name="B", role="Dev")
        db.flush()
        t = create_task(db, project_id=pid, name="Task", assigned_to_id=m1.id)
        db.flush()
        reassign_task(db, t.id, m2.id)
        fetched = get_task(db, t.id)
        assert fetched.assigned_to_id == m2.id

    def test_get_project_tasks(self, db):
        pid = _make_project(db)
        create_task(db, project_id=pid, name="T1")
        create_task(db, project_id=pid, name="T2")
        tasks = get_project_tasks(db, pid)
        assert len(tasks) == 2

    def test_find_blockers_detects_blocked(self, db):
        pid = _make_project(db)
        t = create_task(db, project_id=pid, name="Blocked Task")
        db.flush()
        update_task_status(db, t.id, TaskStatus.blocked)
        blockers = find_blockers(db, pid)
        assert len(blockers) == 1
        assert blockers[0]["name"] == "Blocked Task"


# ── Milestones ────────────────────────────────────────────────────────────────


class TestMilestones:
    def test_create_milestone(self, db):
        pid = _make_project(db)
        m = create_milestone(db, project_id=pid, name="Phase 1", due_date=datetime.date(2026, 12, 31))
        db.flush()
        assert m.id is not None
        assert m.status == MilestoneStatus.pending

    def test_get_project_milestones(self, db):
        pid = _make_project(db)
        create_milestone(db, project_id=pid, name="M1")
        create_milestone(db, project_id=pid, name="M2")
        milestones = get_project_milestones(db, pid)
        assert len(milestones) == 2

    def test_update_milestone_status(self, db):
        pid = _make_project(db)
        m = create_milestone(db, project_id=pid, name="M1")
        db.flush()
        update_milestone_status(db, m.id, MilestoneStatus.achieved)
        milestones = get_project_milestones(db, pid)
        assert milestones[0].status == MilestoneStatus.achieved


# ── Daily Logs ─────────────────────────────────────────────────────────────────


class TestDailyLogs:
    def test_create_daily_log(self, db):
        pid = _make_project(db)
        mid = _make_member(db, pid)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        log = create_daily_log(
            db, task_id=t.id, team_member_id=mid, project_id=pid,
            yesterday_progress="Did work", today_plan="More work",
            blockers="None", hours_logged=8.0,
        )
        db.flush()
        assert log.id is not None
        assert log.yesterday_progress == "Did work"
        assert log.hours_logged == 8.0

    def test_get_project_daily_logs(self, db):
        pid = _make_project(db)
        mid = _make_member(db, pid)
        t = create_task(db, project_id=pid, name="Task")
        db.flush()
        create_daily_log(db, task_id=t.id, team_member_id=mid, project_id=pid)
        create_daily_log(db, task_id=t.id, team_member_id=mid, project_id=pid)
        logs = get_project_daily_logs(db, pid)
        assert len(logs) == 2


# ── Sprint Reports ─────────────────────────────────────────────────────────────


class TestSprintReports:
    def test_save_sprint_report(self, db):
        pid = _make_project(db)
        report = save_sprint_report(
            db, project_id=pid,
            summary="Good sprint", blockers="None",
            estimated_cost_usd=500.0,
        )
        db.flush()
        assert report.id is not None
        assert report.summary == "Good sprint"

    def test_get_sprint_reports(self, db):
        pid = _make_project(db)
        save_sprint_report(db, project_id=pid, summary="Sprint 1")
        save_sprint_report(db, project_id=pid, summary="Sprint 2")
        reports = get_sprint_reports(db, pid)
        assert len(reports) == 2


# ── Issues ─────────────────────────────────────────────────────────────────────


class TestIssues:
    def test_create_issue(self, db):
        pid = _make_project(db)
        issue = create_issue(db, project_id=pid, title="Bug", priority="high")
        db.flush()
        assert issue.id is not None
        assert issue.status == IssueStatus.open

    def test_create_issue_with_description(self, db):
        pid = _make_project(db)
        issue = create_issue(
            db, project_id=pid, title="Bug",
            description="Details here", priority="critical",
        )
        db.flush()
        assert issue.description == "Details here"
        assert issue.priority == IssuePriority.critical

    def test_get_project_issues(self, db):
        pid = _make_project(db)
        create_issue(db, project_id=pid, title="A")
        create_issue(db, project_id=pid, title="B")
        issues = get_project_issues(db, pid)
        assert len(issues) == 2

    def test_filter_issues_by_status(self, db):
        pid = _make_project(db)
        i1 = create_issue(db, project_id=pid, title="Open")
        i2 = create_issue(db, project_id=pid, title="In progress")
        db.flush()
        update_issue_status(db, i2.id, IssueStatus.in_progress)
        open_issues = get_project_issues(db, pid, status=IssueStatus.open)
        in_progress = get_project_issues(db, pid, status=IssueStatus.in_progress)
        assert len(open_issues) == 1
        assert len(in_progress) == 1

    def test_update_issue_status(self, db):
        pid = _make_project(db)
        issue = create_issue(db, project_id=pid, title="Bug")
        db.flush()
        update_issue_status(db, issue.id, IssueStatus.in_progress, resolution_notes="Fixing")
        fetched = get_issue(db, issue.id)
        assert fetched.status == IssueStatus.in_progress
        assert fetched.resolution_notes == "Fixing"

    def test_assign_issue(self, db):
        pid = _make_project(db)
        mid = _make_member(db, pid)
        issue = create_issue(db, project_id=pid, title="Bug")
        db.flush()
        assign_issue(db, issue.id, mid)
        fetched = get_issue(db, issue.id)
        assert fetched.assigned_to_id == mid


# ── Change Requests ────────────────────────────────────────────────────────────


class TestChangeRequests:
    def test_create_cr(self, db):
        pid = _make_project(db)
        cr = create_change_request(
            db, project_id=pid, title="Add SSO",
            justification="Security req", impact_scope="schedule",
        )
        db.flush()
        assert cr.id is not None
        assert cr.status == ChangeRequestStatus.submitted

    def test_get_project_crs(self, db):
        pid = _make_project(db)
        create_change_request(db, project_id=pid, title="CR1")
        create_change_request(db, project_id=pid, title="CR2")
        crs = get_project_change_requests(db, pid)
        assert len(crs) == 2

    def test_update_cr_status_approve(self, db):
        pid = _make_project(db)
        cr = create_change_request(db, project_id=pid, title="CR1")
        db.flush()
        update_change_request_status(db, cr.id, ChangeRequestStatus.approved, approved_by_id=1)
        fetched = get_change_request(db, cr.id)
        assert fetched.status == ChangeRequestStatus.approved

    def test_update_cr_status_reject(self, db):
        pid = _make_project(db)
        cr = create_change_request(db, project_id=pid, title="CR1")
        db.flush()
        update_change_request_status(db, cr.id, ChangeRequestStatus.rejected)
        fetched = get_change_request(db, cr.id)
        assert fetched.status == ChangeRequestStatus.rejected

    def test_filter_crs_by_status(self, db):
        pid = _make_project(db)
        cr1 = create_change_request(db, project_id=pid, title="A")
        cr2 = create_change_request(db, project_id=pid, title="B")
        db.flush()
        update_change_request_status(db, cr1.id, ChangeRequestStatus.approved)
        approved = get_project_change_requests(db, pid, status=ChangeRequestStatus.approved)
        submitted = get_project_change_requests(db, pid, status=ChangeRequestStatus.submitted)
        assert len(approved) == 1
        assert len(submitted) == 1
