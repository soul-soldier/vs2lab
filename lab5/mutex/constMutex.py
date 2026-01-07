# Messages
ENTER = 'ENTER'
ALLOW = 'ALLOW'
RELEASE = 'RELEASE'
# Process behaviors
ACTIVE = 'ACTIVE'
PASSIVE = 'PASSIVE'
BEHAVIOR_TYPES = [ACTIVE, PASSIVE]

# Failure handling (timeout-based suspicion)
# A peer is suspected crashed if it doesn't respond in any way (ENTER/ALLOW/RELEASE)
# while we are waiting to enter the critical section.
RECEIVE_TIMEOUT_SEC = 3
SUSPECT_AFTER_SEC = 6
