import logging
import os
import random

import stablelog

from const3PC import (
    GLOBAL_ABORT,
    GLOBAL_COMMIT,
    PREPARE_COMMIT,
    READY_COMMIT,
    TIMEOUT,
    VOTE_ABORT,
    VOTE_COMMIT,
    VOTE_REQUEST,
)


class Coordinator3PC:
    """Implements a simplified three phase commit coordinator (3PC).

    Notes:
    - Writes state to a stable log.
    - Simulates possible crash failures in INIT, WAIT, and PRECOMMIT.
    - Participant crashes are not explicitly simulated, but timeouts are handled
      according to the termination rules described in the lab handout.
    """

    def __init__(self, chan):
        # similar to 2pc implementation
        # initialize channel, id, participants, stable log, logger, state
        self.channel = chan
        self.coordinator = self.channel.join('coordinator3pc')
        self.participants: set[str] = set()
        self.stable_log = stablelog.create_log('coordinator3pc-' + self.coordinator)
        self.logger = logging.getLogger('vs2lab.lab6.3pc.Coordinator')
        self.state: str | None = None

    def _enter_state(self, state: str) -> None:
        self.stable_log.info(state)
        self.logger.info('Coordinator %s entered state %s.', self.coordinator, state)
        self.state = state

    def init(self) -> None:
        self.channel.bind(self.coordinator)
        self._enter_state('INIT')
        self.participants = self.channel.subgroup('participant3pc')

    def run(self) -> str:
        # Test controls (optional):
        # - VS2LAB_3PC_NO_CRASH=1 disables random crashes
        # - VS2LAB_3PC_CRASH_AT=INIT|WAIT|PRECOMMIT forces a crash at that point
        no_crash = os.getenv('VS2LAB_3PC_NO_CRASH', '').lower() in {'1', 'true', 'yes'}
        crash_at = os.getenv('VS2LAB_3PC_CRASH_AT', '').strip().upper()

        # If a crash point is forced, make the run deterministic by disabling
        # any additional random crashes.
        if crash_at:
            no_crash = True

        # Possible crash before doing anything
        if crash_at == 'INIT':
            return 'Coordinator crashed in state INIT.'
        if (not no_crash) and random.random() > 3 / 4:
            return 'Coordinator crashed in state INIT.'

        # Phase 1a: request votes
        self._enter_state('WAIT')
        self.channel.send_to(self.participants, VOTE_REQUEST)

        # Possible crash after sending vote request
        if crash_at == 'WAIT':
            return 'Coordinator crashed in state WAIT.'
        if (not no_crash) and random.random() > 2 / 3:
            return 'Coordinator crashed in state WAIT.'

        # Phase 1b/2a: collect votes
        yet_to_receive = set(self.participants)
        # waits for votes from all participants until TIMEOUT or VOTE_ABORT
        while yet_to_receive:
            msg = self.channel.receive_from(self.participants, TIMEOUT)
            if (not msg) or (msg[1] == VOTE_ABORT):
                reason = 'timeout' if not msg else 'vote_abort from ' + msg[0]
                # coordinator enters ABORT state and sends GLOBAL_ABORT
                self._enter_state('ABORT')
                self.channel.send_to(self.participants, GLOBAL_ABORT)
                return f'Coordinator {self.coordinator} terminated in state ABORT. Reason: {reason}.'

            assert msg[1] == VOTE_COMMIT
            yet_to_receive.remove(msg[0])

        # Phase 2a: all votes commit => PRECOMMIT
        self._enter_state('PRECOMMIT')
        self.channel.send_to(self.participants, PREPARE_COMMIT)

        # Possible crash after sending prepare-commit
        if crash_at == 'PRECOMMIT':
            return 'Coordinator crashed in state PRECOMMIT.'
        if (not no_crash) and random.random() > 2 / 3:
            return 'Coordinator crashed in state PRECOMMIT.'

        # Phase 3a: collect READY_COMMIT
        yet_to_receive = set(self.participants)
        while yet_to_receive:
            msg = self.channel.receive_from(self.participants, TIMEOUT)
            if not msg:
                # Termination rule (participant crash in PRECOMMIT): commit anyway
                break
            if msg[1] != READY_COMMIT:
                # Ignore unexpected messages (not expected in this simplified model)
                continue
            if msg[0] in yet_to_receive:
                yet_to_receive.remove(msg[0])

        self._enter_state('COMMIT')
        self.channel.send_to(self.participants, GLOBAL_COMMIT)
        return f'Coordinator {self.coordinator} terminated in state COMMIT.'
