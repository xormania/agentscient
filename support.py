"""Expose the task suite's path loader to unittest's repository-root mode."""

from ops.devlane.task.tests.support import APP, REPO, load

__all__ = ["APP", "REPO", "load"]
