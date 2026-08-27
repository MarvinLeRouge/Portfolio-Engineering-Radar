from enum import Enum


class ScoringModel(str, Enum):
    FIXED_SCALE = "FIXED_SCALE"
    STATUS_4STATE = "STATUS_4STATE"


class ScoreLevel(str, Enum):
    CRITERION = "CRITERION"
    CATEGORY = "CATEGORY"
    GLOBAL = "GLOBAL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WONT_FIX = "WONT_FIX"


class HumanVerdict(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceType(str, Enum):
    TOOL_OUTPUT_EXCERPT = "TOOL_OUTPUT_EXCERPT"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"


class RoadmapStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    WONT_FIX = "WONT_FIX"
