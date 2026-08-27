from enum import StrEnum


class ScoringModel(StrEnum):
    FIXED_SCALE = "FIXED_SCALE"
    STATUS_4STATE = "STATUS_4STATE"


class ScoreLevel(StrEnum):
    CRITERION = "CRITERION"
    CATEGORY = "CATEGORY"
    GLOBAL = "GLOBAL"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WONT_FIX = "WONT_FIX"


class HumanVerdict(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceType(StrEnum):
    TOOL_OUTPUT_EXCERPT = "TOOL_OUTPUT_EXCERPT"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"


class RoadmapStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    WONT_FIX = "WONT_FIX"
