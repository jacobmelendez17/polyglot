"""Shared enums used across models and domain logic."""
import enum


class UserRole(str, enum.Enum):
    user = "user"
    beta_tester = "beta_tester"
    moderator = "moderator"
    content_editor = "content_editor"
    admin = "admin"
    owner = "owner"


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class ItemType(str, enum.Enum):
    vocabulary = "vocabulary"
    grammar = "grammar"


class CurriculumMode(str, enum.Enum):
    default_dispersed = "default_dispersed"      # grammar dispersed across the 4 themed lessons
    grammar_batch = "grammar_batch"              # 4 vocab lessons + 1 grammar lesson
    fully_dispersed = "fully_dispersed"          # grammar + vocab mixed across 5 batches


class LessonKind(str, enum.Enum):
    themed_vocab = "themed_vocab"
    grammar_batch = "grammar_batch"
    mixed = "mixed"


class Gender(str, enum.Enum):
    masculine = "masculine"
    feminine = "feminine"
    both = "both"
    neutral = "neutral"
    none = "none"


class Article(str, enum.Enum):
    el = "el"
    la = "la"
    los = "los"
    las = "las"
    un = "un"
    una = "una"
    none = "none"


class PracticeCategory(str, enum.Enum):
    sentences = "sentences"
    listening = "listening"
    speaking = "speaking"


class LeechState(str, enum.Enum):
    none = "none"
    watch = "watch"
    leech = "leech"
    critical = "critical"
