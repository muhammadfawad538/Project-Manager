# Line ending: LF
# Encoding: UTF-8

"""Tests for the CPM (Critical Path Method) algorithm."""

from __future__ import annotations

import pytest

from pmagent.main import compute_critical_path


# ── Basic CPM Tests ────────────────────────────────────────────────────────────


class TestComputeCriticalPath:
    def test_returns_expected_keys(self):
        tasks = [
            {"id": "1", "name": "Task A", "estimated_hours": 8, "dependencies": []},
        ]
        result = compute_critical_path(tasks)
        assert "critical_path" in result
        assert "total_duration_days" in result
        assert "all_floats" in result
        assert "total_estimated_hours" in result

    def test_single_task_is_critical(self):
        tasks = [
            {"id": "1", "name": "Only task", "estimated_hours": 8, "dependencies": []},
        ]
        result = compute_critical_path(tasks)
        assert result["critical_path"] == ["1"]
        assert result["all_floats"]["1"] == 0.0

    def test_linear_chain_all_critical(self):
        """A straight line of dependencies: every task is on the critical path."""
        tasks = [
            {"id": "1", "name": "Start", "estimated_hours": 8, "dependencies": []},
            {"id": "2", "name": "Middle", "estimated_hours": 16, "dependencies": ["1"]},
            {"id": "3", "name": "End", "estimated_hours": 8, "dependencies": ["2"]},
        ]
        result = compute_critical_path(tasks)
        assert result["critical_path"] == ["1", "2", "3"]

    def test_parallel_tasks_only_one_critical(self):
        """Two tasks after the same dependency: only the longer one is critical."""
        tasks = [
            {"id": "1", "name": "Dep", "estimated_hours": 8, "dependencies": []},
            {"id": "2", "name": "Short", "estimated_hours": 8, "dependencies": ["1"]},
            {"id": "3", "name": "Long", "estimated_hours": 40, "dependencies": ["1"]},
        ]
        result = compute_critical_path(tasks)
        # Task 3 is longer, so it's critical; Task 2 has float
        assert "3" in result["critical_path"]
        assert result["all_floats"]["3"] == 0.0
        assert result["all_floats"]["2"] > 0

    def test_project_duration_is_positive(self):
        tasks = [
            {"id": "1", "name": "A", "estimated_hours": 16, "dependencies": []},
            {"id": "2", "name": "B", "estimated_hours": 24, "dependencies": ["1"]},
        ]
        result = compute_critical_path(tasks)
        assert result["total_duration_days"] > 0

    def test_all_floats_summary(self):
        """all_floats should contain every task ID."""
        tasks = [
            {"id": "1", "name": "A", "estimated_hours": 8, "dependencies": []},
            {"id": "2", "name": "B", "estimated_hours": 8, "dependencies": ["1"]},
        ]
        result = compute_critical_path(tasks)
        assert set(result["all_floats"].keys()) == {"1", "2"}
        assert all(isinstance(v, float) for v in result["all_floats"].values())

    def test_diamond_dependency_pattern(self):
        """Diamond: 1 -> 2, 1 -> 3, 2 -> 4, 3 -> 4.

        The longer branch is critical, the shorter has float.
        """
        tasks = [
            {"id": "1", "name": "Start", "estimated_hours": 8, "dependencies": []},
            {"id": "2", "name": "Short", "estimated_hours": 8, "dependencies": ["1"]},
            {"id": "3", "name": "Long", "estimated_hours": 40, "dependencies": ["1"]},
            {"id": "4", "name": "Merge", "estimated_hours": 8, "dependencies": ["2", "3"]},
        ]
        result = compute_critical_path(tasks)
        # Path through 3 is critical, path through 2 has float
        assert "1" in result["critical_path"]
        assert "3" in result["critical_path"]
        assert "4" in result["critical_path"]
        assert result["all_floats"]["2"] > 0

    def test_float_is_non_negative(self):
        """No task should have negative float in a valid DAG."""
        tasks = [
            {"id": "1", "name": "A", "estimated_hours": 8, "dependencies": []},
            {"id": "2", "name": "B", "estimated_hours": 16, "dependencies": ["1"]},
            {"id": "3", "name": "C", "estimated_hours": 8, "dependencies": ["2"]},
        ]
        result = compute_critical_path(tasks)
        assert all(v >= 0 for v in result["all_floats"].values())

    def test_empty_task_list(self):
        result = compute_critical_path([])
        assert result["critical_path"] == []
        assert result["total_duration_days"] == 0.0

    def test_minimum_duration_is_half_day(self):
        """Even 0 hours gets bumped to 0.5 days."""
        tasks = [
            {"id": "1", "name": "Quick", "estimated_hours": 0, "dependencies": []},
        ]
        result = compute_critical_path(tasks)
        assert result["total_duration_days"] >= 0.5
