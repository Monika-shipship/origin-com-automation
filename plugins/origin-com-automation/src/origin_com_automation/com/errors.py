"""Typed failures crossing the COM and MCP boundaries."""

from __future__ import annotations


class OriginAutomationError(RuntimeError):
    code = "ORIGIN_AUTOMATION_ERROR"
    retryable = False

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class WorkerNotRunningError(OriginAutomationError):
    code = "WORKER_NOT_RUNNING"


class OriginTimeoutError(OriginAutomationError):
    code = "COM_TIMEOUT"
    retryable = True


class AttachedSessionProtectedError(OriginAutomationError):
    code = "ATTACHED_SESSION_PROTECTED"


class SessionNotFoundError(OriginAutomationError):
    code = "SESSION_NOT_FOUND"


class NoActiveSessionError(OriginAutomationError):
    code = "NO_ACTIVE_SESSION"


class OwnershipUnverifiedError(OriginAutomationError):
    code = "OWNERSHIP_UNVERIFIED"


class NoExistingOriginError(OriginAutomationError):
    code = "NO_EXISTING_ORIGIN"


class LabTalkExecutionError(OriginAutomationError):
    code = "LABTALK_EXECUTION_FAILED"


class ProjectSaveUnconfirmedError(OriginAutomationError):
    code = "PROJECT_SAVE_UNCONFIRMED"


class ProjectCloseUnconfirmedError(OriginAutomationError):
    code = "PROJECT_CLOSE_UNCONFIRMED"


class AnalysisExecutionError(OriginAutomationError):
    code = "ANALYSIS_FAILED"
