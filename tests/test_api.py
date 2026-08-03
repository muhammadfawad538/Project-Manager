# Line ending: LF
# Encoding: UTF-8

"""Tests for the FastAPI REST API — health, issues, and change request endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from pmagent.db.models import IssueStatus, ChangeRequestStatus
from pmagent.db.repository import create_project, add_team_member
from pmagent.db.session import get_session


@pytest.fixture()
def api_client():
    """Provide an async test client for the FastAPI app."""
    from api.main import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
async def seeded_project():
    """Create a project with a team member directly in the DB, return project_id."""
    with get_session() as s:
        p = create_project(s, name="API Test Project", project_type="IT", industry="Tech")
        add_team_member(s, project_id=p.id, name="API Tester", role="PM")
        return p.id


# ── Health Endpoint ────────────────────────────────────────────────────────────


class TestHealth:
    async def test_health_returns_ok(self, api_client):
        resp = await api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "pmagent"


# ── Issue Endpoints ────────────────────────────────────────────────────────────


class TestIssueEndpoints:
    async def test_list_issues_empty(self, api_client, seeded_project):
        resp = await api_client.get(f"/projects/{seeded_project}/issues")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["issues"] == []

    async def test_create_issue(self, api_client, seeded_project):
        resp = await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Login timeout", "priority": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Login timeout"
        assert data["priority"] == "critical"
        assert data["status"] == "open"
        assert "id" in data

    async def test_list_issues_after_create(self, api_client, seeded_project):
        await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug 1", "priority": "high"},
        )
        await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug 2", "priority": "medium"},
        )
        resp = await api_client.get(f"/projects/{seeded_project}/issues")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    async def test_filter_issues_by_status(self, api_client, seeded_project):
        create_resp = await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug"},
        )
        issue_id = create_resp.json()["id"]

        await api_client.put(
            f"/issues/{issue_id}/status",
            json={"status": "in_progress"},
        )

        resp_open = await api_client.get(f"/projects/{seeded_project}/issues?status=open")
        resp_ip = await api_client.get(f"/projects/{seeded_project}/issues?status=in_progress")

        assert resp_open.json()["count"] == 0
        assert resp_ip.json()["count"] == 1

    async def test_update_issue_status(self, api_client, seeded_project):
        create_resp = await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug"},
        )
        issue_id = create_resp.json()["id"]

        resp = await api_client.put(
            f"/issues/{issue_id}/status",
            json={"status": "resolved", "resolution_notes": "Fixed in v2"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_assign_issue(self, api_client, seeded_project):
        with get_session() as s:
            member = add_team_member(s, project_id=seeded_project, name="Dev", role="Dev")
            member_id = member.id

        create_resp = await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug"},
        )
        issue_id = create_resp.json()["id"]

        resp = await api_client.put(
            f"/issues/{issue_id}/assign",
            json={"member_id": member_id},
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_to_id"] == member_id

    async def test_update_nonexistent_issue_returns_404(self, api_client):
        resp = await api_client.put(
            "/issues/99999/status",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    async def test_invalid_status_returns_400(self, api_client, seeded_project):
        create_resp = await api_client.post(
            f"/projects/{seeded_project}/issues",
            json={"title": "Bug"},
        )
        issue_id = create_resp.json()["id"]
        resp = await api_client.put(
            f"/issues/{issue_id}/status",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 400


# ── Change Request Endpoints ──────────────────────────────────────────────────


class TestChangeRequestEndpoints:
    async def test_list_crs_empty(self, api_client, seeded_project):
        resp = await api_client.get(f"/projects/{seeded_project}/change-requests")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    async def test_create_cr(self, api_client, seeded_project):
        resp = await api_client.post(
            f"/projects/{seeded_project}/change-requests",
            json={
                "title": "Add SSO",
                "justification": "Security requirement",
                "impact_scope": "schedule",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Add SSO"
        assert data["status"] == "submitted"
        assert data["impact_scope"] == "schedule"

    async def test_list_crs_after_create(self, api_client, seeded_project):
        await api_client.post(
            f"/projects/{seeded_project}/change-requests",
            json={"title": "CR1", "impact_scope": "scope"},
        )
        await api_client.post(
            f"/projects/{seeded_project}/change-requests",
            json={"title": "CR2", "impact_scope": "budget"},
        )
        resp = await api_client.get(f"/projects/{seeded_project}/change-requests")
        assert resp.json()["count"] == 2

    async def test_approve_cr(self, api_client, seeded_project):
        create_resp = await api_client.post(
            f"/projects/{seeded_project}/change-requests",
            json={"title": "CR1"},
        )
        cr_id = create_resp.json()["id"]

        resp = await api_client.put(
            f"/change-requests/{cr_id}/status",
            json={"status": "approved", "approved_by_id": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_reject_cr(self, api_client, seeded_project):
        create_resp = await api_client.post(
            f"/projects/{seeded_project}/change-requests",
            json={"title": "CR1"},
        )
        cr_id = create_resp.json()["id"]

        resp = await api_client.put(
            f"/change-requests/{cr_id}/status",
            json={"status": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_filter_crs_by_status(self, api_client, seeded_project):
        create1 = await api_client.post(
            f"/projects/{seeded_project}/change-requests", json={"title": "A"}
        )
        await api_client.post(
            f"/projects/{seeded_project}/change-requests", json={"title": "B"}
        )
        await api_client.put(
            f"/change-requests/{create1.json()['id']}/status",
            json={"status": "approved"},
        )

        approved = await api_client.get(
            f"/projects/{seeded_project}/change-requests?status=approved"
        )
        submitted = await api_client.get(
            f"/projects/{seeded_project}/change-requests?status=submitted"
        )
        assert approved.json()["count"] == 1
        assert submitted.json()["count"] == 1
