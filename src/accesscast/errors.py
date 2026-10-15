"""Exit codes (CLAUDE.md §6) and the exceptions that map onto them."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2
    CONFIG = 3
    MISSING_DEPENDENCY = 4
    MODEL_ENDPOINT = 5
    OUT_OF_MEMORY = 6
    VALIDATION_FAILED = 7
    MEDIA = 8
    PARTIAL = 10
    INTERRUPTED = 130


class AccessCastError(Exception):
    exit_code: ExitCode = ExitCode.VALIDATION_FAILED

    def __init__(self, message: str, *, code: ExitCode | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.exit_code = code


class UsageError(AccessCastError):
    exit_code = ExitCode.USAGE


class ConfigError(AccessCastError):
    exit_code = ExitCode.CONFIG


class MissingDependencyError(AccessCastError):
    exit_code = ExitCode.MISSING_DEPENDENCY


class ModelEndpointError(AccessCastError):
    exit_code = ExitCode.MODEL_ENDPOINT


class OutOfMemoryError(AccessCastError):
    exit_code = ExitCode.OUT_OF_MEMORY


class ValidationFailed(AccessCastError):
    exit_code = ExitCode.VALIDATION_FAILED


class MediaError(AccessCastError):
    exit_code = ExitCode.MEDIA


class PartialResult(AccessCastError):
    exit_code = ExitCode.PARTIAL


class LlmOutputError(AccessCastError):
    """Malformed or schema-invalid model output. Always fails closed."""

    exit_code = ExitCode.VALIDATION_FAILED


class UnknownLanguageError(UsageError):
    """No silent fallback to English (CLAUDE.md rule 6)."""
