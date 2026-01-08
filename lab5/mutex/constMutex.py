# Messages
ENTER = 'ENTER'
ALLOW = 'ALLOW'
RELEASE = 'RELEASE'
HEARTBEAT = 'HEARTBEAT'
# Process behaviors
ACTIVE = 'ACTIVE'
PASSIVE = 'PASSIVE'
BEHAVIOR_TYPES = [ACTIVE, PASSIVE]

# Failure handling (timeout-based suspicion)
# A peer is suspected crashed if it doesn't respond in any way (ENTER/ALLOW/RELEASE)
# while we are waiting to enter the critical section.
RECEIVE_TIMEOUT_SEC = 4
SUSPECT_AFTER_SEC = 8

# Heartbeats for crash suspicion
HEARTBEAT_INTERVAL_SEC = 1.5
HEARTBEAT_GRACE_SEC = 5
