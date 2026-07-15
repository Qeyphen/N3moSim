# Mission state machine state
int8 IDLE = 0
int8 NAVIGATING = 1
int8 FINISHED = 2
int8 ABORTED = 3

int8 state          # current state (one of the constants above)
int32 goal_index    # index of the active goal in the goal list
