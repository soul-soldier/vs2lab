# coordinator -> participant messages
VOTE_REQUEST = 'VOTE_REQUEST'
PREPARE_COMMIT = 'PREPARE_COMMIT'
GLOBAL_COMMIT = 'GLOBAL_COMMIT'
GLOBAL_ABORT = 'GLOBAL_ABORT'

# participant -> coordinator messages
VOTE_COMMIT = 'VOTE_COMMIT'
VOTE_ABORT = 'VOTE_ABORT'
READY_COMMIT = 'READY_COMMIT'

# termination / coordinator-election messages
NEW_COORDINATOR = 'NEW_COORDINATOR'

# participant decisions
LOCAL_ABORT = 'LOCAL_ABORT'
LOCAL_SUCCESS = 'LOCAL_SUCCESS'

# fail-noisy crash timeout
TIMEOUT = 1
