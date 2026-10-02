"""The teacher: how Learning mode reaches Claude. Pick the route in .env (TEACHER=...)."""
from .. import config
from .base import AskRequest, Teacher, TeacherError


def make_teacher() -> Teacher:
    if config.TEACHER == "api":
        from .api import ApiTeacher
        return ApiTeacher()
    from .claude_code import ClaudeCodeTeacher
    return ClaudeCodeTeacher()


__all__ = ["AskRequest", "Teacher", "TeacherError", "make_teacher"]
