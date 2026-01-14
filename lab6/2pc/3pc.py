"""Application performing a distributed commitment using 3PC.

- Sets up a group of participants.
- Participants want to jointly commit all of their local activities or none.
- Participants and coordinator run in separate OS processes.

Run (with Redis running):
    pipenv run python 3pc.py

Deterministic commit test (no crashes + all participants succeed):
    VS2LAB_3PC_NO_CRASH=1 VS2LAB_3PC_FORCE_SUCCESS=1 pipenv run python 3pc.py
"""

import logging
import multiprocessing as mp

import coordinator3pc
import participant3pc
from context import lab_channel, lab_logging

lab_logging.setup(stream_level=logging.INFO, file_level=logging.DEBUG)

logger = logging.getLogger('vs2lab.lab6.3pc.3pc')


def create_and_run(num_bits, proc_class, enter_bar, run_bar):
    chan = lab_channel.Channel(n_bits=num_bits)
    proc = proc_class(chan)
    enter_bar.wait()
    proc.init()
    run_bar.wait()
    logger.info(proc.run())


if __name__ == '__main__':
    m = 8
    n = 3

    # Flush communication channel
    chan = lab_channel.Channel()
    chan.channel.flushall()

    mp.set_start_method('spawn')

    bar1 = mp.Barrier(n + 1)
    bar2 = mp.Barrier(n + 1)

    participants = []
    for i in range(n):
        p = mp.Process(
            target=create_and_run,
            name='Participant3PC-' + str(i),
            args=(m, participant3pc.Participant3PC, bar1, bar2),
        )
        participants.append(p)
        p.start()

    c = mp.Process(
        target=create_and_run,
        name='Coordinator3PC',
        args=(m, coordinator3pc.Coordinator3PC, bar1, bar2),
    )
    c.start()

    c.join()
    for p in participants:
        p.join()
