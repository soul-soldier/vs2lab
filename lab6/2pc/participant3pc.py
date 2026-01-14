import logging
import os
import random
from dataclasses import dataclass

import stablelog

from const3PC import (
    GLOBAL_ABORT,
    GLOBAL_COMMIT,
    NEW_COORDINATOR,
    PREPARE_COMMIT,
    READY_COMMIT,
    TIMEOUT,
    VOTE_ABORT,
    VOTE_COMMIT,
    VOTE_REQUEST,
    LOCAL_ABORT,
    LOCAL_SUCCESS,
)


@dataclass(frozen=True)
class CoordinatorAnnouncement:
    kind: str
    coordinator_state: str
    coordinator_id: str


def _min_pid(pids: set[str]) -> str:
    return min(pids, key=lambda pid: int(pid))


def _state_rank(state: str) -> int:
    # Higher means "later" / more final.
    return {
        'INIT': 0,
        'READY': 1,
        'PRECOMMIT': 2,
        'COMMIT': 3,
        'ABORT': 3,
    }.get(state, 0)


class Participant3PC:
    """Implements a simplified three phase commit participant (3PC).

    Features:
    - Basic 3PC state machine (INIT -> READY -> PRECOMMIT -> COMMIT).
    - Terminates after coordinator crash using a deterministic new coordinator
      (participant with smallest numeric pid).
    - Ignores message loss and multiple concurrent crashes (per assignment).
    """

    def __init__(self, chan):
        self.channel = chan
        self.participant = self.channel.join('participant3pc')
        self.stable_log = stablelog.create_log('participant3pc-' + self.participant)
        self.logger = logging.getLogger('vs2lab.lab6.3pc.Participant')
        self.coordinator: set[str] = set()
        self.all_participants: set[str] = set()
        self.state: str = 'NEW'

    @staticmethod
    def _do_work() -> str:
        force_success = os.getenv('VS2LAB_3PC_FORCE_SUCCESS', '').lower() in {'1', 'true', 'yes'}
        if force_success:
            return LOCAL_SUCCESS
        return LOCAL_ABORT if random.random() > 2 / 3 else LOCAL_SUCCESS

    def _enter_state(self, state: str) -> None:
        self.stable_log.info(state)
        self.logger.info('Participant %s entered state %s.', self.participant, state)
        self.state = state

    def init(self) -> None:
        self.channel.bind(self.participant)
        self.coordinator = self.channel.subgroup('coordinator3pc')
        self.all_participants = self.channel.subgroup('participant3pc')
        self._enter_state('INIT')

    def _broadcast_new_coordinator(self, coordinator_state: str, leader: str) -> None:
        ann = CoordinatorAnnouncement(NEW_COORDINATOR, coordinator_state, leader)
        self.channel.send_to(self.all_participants, ann)

    def _receive_decision_after_crash(self) -> str:
        """Termination protocol after coordinator crash.

        Triggered when we are in READY or PRECOMMIT and the coordinator stops responding.
        Deterministic election: participant with smallest numeric pid becomes new coordinator.

        Returns: GLOBAL_COMMIT or GLOBAL_ABORT
        """
        leader = _min_pid(self.all_participants)

        # If we are the elected new coordinator.
        if self.participant == leader:
            # Map our participant state to coordinator-termination state.
            if self.state == 'READY':
                coord_state = 'WAIT'
            elif self.state == 'PRECOMMIT':
                coord_state = 'PRECOMMIT'
            elif self.state in ('COMMIT', 'ABORT'):
                coord_state = self.state
            else:
                coord_state = 'WAIT'

            self.logger.info('Elected new coordinator %s in state %s.', leader, coord_state)
            self._broadcast_new_coordinator(coord_state, leader)

            # Decide according to lab handout.
            if coord_state == 'WAIT':
                # Abort; PRECOMMIT participants may abort only during termination.
                self.channel.send_to(self.all_participants, GLOBAL_ABORT)
                return GLOBAL_ABORT

            if coord_state == 'PRECOMMIT':
                self.channel.send_to(self.all_participants, GLOBAL_COMMIT)
                return GLOBAL_COMMIT

            if coord_state == 'COMMIT':
                self.channel.send_to(self.all_participants, GLOBAL_COMMIT)
                return GLOBAL_COMMIT

            # coord_state == 'ABORT' or anything else
            self.channel.send_to(self.all_participants, GLOBAL_ABORT)
            return GLOBAL_ABORT

        # Otherwise: wait for elected leader's termination decision.
        # Messages are persistent in redis queues, so we can just block for a bit.
        seen_announcement: str | None = None
        deadline_loops = 10  # bounded; multiple crashes ignored in this lab
        while deadline_loops > 0:
            deadline_loops -= 1

            msg = self.channel.receive_from_any(TIMEOUT)
            if not msg:
                continue

            _sender, payload = msg

            # Late messages from the original coordinator are still acceptable.
            if payload in (GLOBAL_COMMIT, GLOBAL_ABORT):
                return payload
            if payload == PREPARE_COMMIT and self.state == 'READY':
                # Old coordinator recovered / message was delayed; continue safely.
                self._enter_state('PRECOMMIT')
                self.channel.send_to(self.coordinator, READY_COMMIT)
                # Now wait for final decision.
                continue

            if isinstance(payload, CoordinatorAnnouncement) and payload.kind == NEW_COORDINATOR:
                if payload.coordinator_id != leader:
                    continue

                seen_announcement = payload.coordinator_state

                # State alignment (only if we are "behind")
                if payload.coordinator_state == 'PRECOMMIT' and self.state == 'READY':
                    self._enter_state('PRECOMMIT')
                    # Optional ack for realism
                    self.channel.send_to({leader}, READY_COMMIT)

                # If leader announces WAIT we do not downgrade PRECOMMIT here;
                # we only allow ABORT once GLOBAL_ABORT arrives.
                continue

            # ignore everything else

        # If we didn't get anything conclusive, default safe outcome.
        # - From READY: abort is safe.
        # - From PRECOMMIT: commit is safe (but we might have missed it).
        return GLOBAL_ABORT if self.state != 'PRECOMMIT' else GLOBAL_COMMIT

    def run(self) -> str:
        # Phase 1b: wait for vote request
        msg = self.channel.receive_from(self.coordinator, TIMEOUT)
        if not msg:
            self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state ABORT (coordinator crash in INIT).'

        assert msg[1] == VOTE_REQUEST

        # Local work
        decision = self._do_work()
        if decision == LOCAL_ABORT:
            self.channel.send_to(self.coordinator, VOTE_ABORT)
            self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state ABORT due to LOCAL_ABORT.'

        # Vote commit
        self._enter_state('READY')
        self.channel.send_to(self.coordinator, VOTE_COMMIT)

        # Wait for PREPARE_COMMIT / GLOBAL_ABORT
        msg = self.channel.receive_from(self.coordinator, TIMEOUT)
        if not msg:
            # Coordinator crash while we are READY
            outcome = self._receive_decision_after_crash()
            if outcome == GLOBAL_COMMIT:
                self._enter_state('COMMIT')
            else:
                self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state {self.state} via termination (READY).' 

        if msg[1] == GLOBAL_ABORT:
            self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state ABORT due to GLOBAL_ABORT.'

        assert msg[1] == PREPARE_COMMIT
        self._enter_state('PRECOMMIT')
        self.channel.send_to(self.coordinator, READY_COMMIT)

        # Wait for GLOBAL_COMMIT
        msg = self.channel.receive_from(self.coordinator, TIMEOUT)
        if not msg:
            # Coordinator crash while we are PRECOMMIT
            outcome = self._receive_decision_after_crash()
            if outcome == GLOBAL_COMMIT:
                self._enter_state('COMMIT')
            else:
                # Allowed only during termination
                self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state {self.state} via termination (PRECOMMIT).'

        if msg[1] == GLOBAL_COMMIT:
            self._enter_state('COMMIT')
            return f'Participant {self.participant} terminated in state COMMIT.'

        # Unexpected fallback
        if msg[1] == GLOBAL_ABORT:
            self._enter_state('ABORT')
            return f'Participant {self.participant} terminated in state ABORT.'

        self._enter_state('ABORT')
        return f'Participant {self.participant} terminated in state ABORT (unexpected message {msg[1]}).'
