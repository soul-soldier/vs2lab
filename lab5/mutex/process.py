import logging
import random
import time

from constMutex import (
    ENTER,
    RELEASE,
    ALLOW,
    ACTIVE,
    RECEIVE_TIMEOUT_SEC,
    SUSPECT_AFTER_SEC,
)


class Process:
    """
    Implements access management to a critical section (CS) via fully
    distributed mutual exclusion (MUTEX).

    Processes broadcast messages (ENTER, ALLOW, RELEASE) timestamped with
    logical (lamport) clocks. All messages are stored in local queues sorted by
    logical clock time.

    Processes follow different behavioral patterns. An ACTIVE process competes 
    with others for accessing the critical section. A PASSIVE process will never 
    request to enter the critical section itself but will allow others to do so.

    A process broadcasts an ENTER request if it wants to enter the CS. A process
    that doesn't want to ENTER replies with an ALLOW broadcast. A process that
    wants to ENTER and receives another ENTER request replies with an ALLOW
    broadcast (which is then later in time than its own ENTER request).

    A process enters the CS if a) its ENTER message is first in the queue (it is
    the oldest pending message) AND b) all other processes have sent messages
    that are younger (either ENTER or ALLOW). RELEASE requests purge
    corresponding ENTER requests from the top of the local queues.

    Message Format:

    <Message>: (Timestamp, Process_ID, <Request_Type>)

    <Request Type>: ENTER | ALLOW  | RELEASE

    """

    def __init__(self, chan):
        self.channel = chan  # Create ref to actual channel
        self.process_id = self.channel.join('proc')  # Find out who you are
        self.all_processes: list = []  # All procs in the proc group
        self.other_processes: list = []  # Needed to multicast to others
        self.queue = []  # The request queue list
        self.clock = 0  # The current logical clock
        self.peer_name = 'unassigned'  # The original peer name
        self.peer_type = 'unassigned'  # A flag indicating behavior pattern
        self.waiting_since: float | None = None  # wall-clock time when we requested ENTER
        self.logger = logging.getLogger("vs2lab.lab5.mutex.process.Process")

    def __mapid(self, id='-1'):
        # format channel member address
        if id == '-1':
            id = self.process_id
        return 'Proc-'+str(id)

    def __cleanup_queue(self):
        if len(self.queue) > 0:
            # self.queue.sort(key = lambda tup: tup[0])
            self.queue.sort()
            # There should never be old ALLOW messages at the head of the queue
            while self.queue[0][2] == ALLOW:
                del (self.queue[0])
                if len(self.queue) == 0:
                    break

    # remove all queued messages of a given process from the queue
    def __purge_process_from_queue(self, pid: str) -> None:
        if not self.queue:
            return
        before = len(self.queue)
        self.queue = [msg for msg in self.queue if msg[1] != pid]
        after = len(self.queue)
        if before != after:
            self.logger.info(
                "{} purged {} queued messages from {} (queue size {} -> {}).".format(
                    self.__mapid(), before - after, self.__mapid(pid), before, after
                )
            )

    def __mark_suspected_crash(self, pid: str, reason: str) -> None:
        if pid not in self.all_processes:
            return

        if pid == self.process_id:
            return

        self.logger.warning(
            "{} suspects {} has crashed ({}).".format(self.__mapid(), self.__mapid(pid), reason)
        )

        # Remove from membership lists used for coordination
        if pid in self.other_processes:
            self.other_processes.remove(pid)
        if pid in self.all_processes:
            self.all_processes.remove(pid)

        # Remove all queued requests from the suspected peer.
        self.__purge_process_from_queue(pid)
        self.__cleanup_queue()

    def __request_to_enter(self):
        self.clock = self.clock + 1  # Increment clock value
        request_msg = (self.clock, self.process_id, ENTER)
        self.queue.append(request_msg)  # Append request to queue
        self.__cleanup_queue()  # Sort the queue
        self.channel.send_to(self.other_processes, request_msg)  # Send request
        self.waiting_since = time.monotonic()

    def __allow_to_enter(self, requester):
        self.clock = self.clock + 1  # Increment clock value
        msg = (self.clock, self.process_id, ALLOW)
        self.channel.send_to([requester], msg)  # Permit other

    def __release(self):
        # need to be first in queue to issue a release
        assert self.queue[0][1] == self.process_id, 'State error: inconsistent local RELEASE'

        # construct new queue from later ENTER requests (removing all ALLOWS)
        tmp = [r for r in self.queue[1:] if r[2] == ENTER]
        self.queue = tmp  # and copy to new queue
        self.clock = self.clock + 1  # Increment clock value
        msg = (self.clock, self.process_id, RELEASE)
        # Multicast release notification
        self.channel.send_to(self.other_processes, msg)
        self.waiting_since = None

    def __allowed_to_enter(self):
        # See who has sent a message (the set will hold at most one element per sender)
        processes_with_later_message = set([req[1] for req in self.queue[1:]])
        # Access granted if this process is first in queue and all others have answered (logically) later
        first_in_queue = self.queue[0][1] == self.process_id
        all_have_answered = len(self.other_processes) == len(
            processes_with_later_message)
        return first_in_queue and all_have_answered

    # Suspect peers that didn't respond after a certain timout period while process is waiting to ENTER CS
    def __suspect_unresponsive_peers(self) -> None:

        if self.waiting_since is None:
            return
        if not self.queue:
            return

        # Only suspect while process is waiting to ENTER CS
        if self.queue[0][1] != self.process_id and not any(
            msg[1] == self.process_id and msg[2] == ENTER for msg in self.queue
        ):
            return

        elapsed = time.monotonic() - self.waiting_since
        if elapsed < SUSPECT_AFTER_SEC:
            return

        # find who responded with any message after first message in queue -> process still responsive
        responded = set([req[1] for req in self.queue[1:]])
        missing = [pid for pid in list(self.other_processes) if pid not in responded]
        for pid in missing:
            self.__mark_suspected_crash(pid, f"no response after {elapsed:.1f}s")

    def __receive(self):
        # Pick up any message (but only wait until timeout)
        _receive = self.channel.receive_from(self.other_processes, RECEIVE_TIMEOUT_SEC)

        if _receive:
            msg = _receive[1] # msg = timestamp, process_id, request_type
            sender = _receive[0] # Channel ID sender

            self.clock = max(self.clock, msg[0])  # Adjust clock value (compare timestamps -> synchronize)
            self.clock = self.clock + 1  # ...and increment

            self.logger.debug("{} received {} from {}.".format(
                self.__mapid(),
                "ENTER" if msg[2] == ENTER
                else "ALLOW" if msg[2] == ALLOW
                else "RELEASE", self.__mapid(msg[1])))

            if msg[2] == ENTER:
                self.queue.append(msg)  # Append an ENTER request
                # and unconditionally allow (don't want to access CS oneself)
                self.__allow_to_enter(msg[1])
            elif msg[2] == ALLOW:
                self.queue.append(msg)  # Append an ALLOW
            elif msg[2] == RELEASE:
                # Remove the releasing process ENTER msg if it exists
                removed = False
                for i, req in enumerate(list(self.queue)):
                    if req[1] == msg[1] and req[2] == ENTER:
                        del self.queue[i]
                        removed = True
                        break
                if not removed:
                    self.logger.info(
                        "{} received RELEASE from {}, but no matching ENTER was queued (ignored).".format(
                            self.__mapid(), self.__mapid(msg[1])
                        )
                    )

            self.__cleanup_queue()  # Finally sort and cleanup the queue
            # If we hear from a previously missing peer, it is by definition responsive
            # this solution doesn't re-add peers once suspected
            if sender in self.other_processes:
                pass
        else:
            self.logger.info("{} timed out on RECEIVE. Local queue: {}".
                             format(self.__mapid(),
                                    list(map(lambda msg: (
                                        'Clock '+str(msg[0]),
                                        self.__mapid(msg[1]),
                                        msg[2]), self.queue))))
            self.__suspect_unresponsive_peers()

    def init(self, peer_name, peer_type):
        self.channel.bind(self.process_id)

        self.all_processes = list(self.channel.subgroup('proc'))
        # sort string elements by numerical order
        self.all_processes.sort(key=lambda x: int(x))

        self.other_processes = list(self.channel.subgroup('proc'))
        self.other_processes.remove(self.process_id)

        self.peer_name = peer_name  # assign peer name
        self.peer_type = peer_type  # assign peer behavior

        self.logger.info("{} joined channel as {}.".format(
            peer_name, self.__mapid()))

    def run(self):
        while True:
            # Enter the critical section if
            # 1) there are more than one process left and
            # 2) this peer has active behavior and
            # 3) random is true
            if len(self.all_processes) > 1 and \
                    self.peer_type == ACTIVE and \
                    random.choice([True, False]):
                self.logger.debug("{} wants to ENTER CS at CLOCK {}."
                                  .format(self.__mapid(), self.clock))

                self.__request_to_enter()
                while not self.__allowed_to_enter():
                    self.__receive()

                # Stay in CS for some time ...
                sleep_time = random.randint(0, 2000)
                self.logger.debug("{} enters CS for {} milliseconds."
                                  .format(self.__mapid(), sleep_time))
                print(" CS <- {}".format(self.__mapid()))
                time.sleep(sleep_time/1000)

                # ... then leave CS
                print(" CS -> {}".format(self.__mapid()))
                self.__release()
                continue

            # Occasionally serve requests to enter (
            if random.choice([True, False]):
                self.__receive()
