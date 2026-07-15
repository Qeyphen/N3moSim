from enum import IntEnum

# ATTENTION - Ros messages should have same enum int ids and this is done manually. No automatic matching ny enum name.


class PlanState(IntEnum):
    """Mirrors PlanState.msg constants."""

    IDLE = 0
    TRACKING = 1
    ARRIVED = 2


class MissionState(IntEnum):
    """Mirrors MissionState.msg constants."""

    IDLE = 0
    NAVIGATING = 1
    FINISHED = 2
    ABORTED = 3
