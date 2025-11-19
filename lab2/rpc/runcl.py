import rpc
import logging
import time

from context import lab_logging

lab_logging.setup(stream_level=logging.INFO)
logger = logging.getLogger('vs2lab.lab2.rpc.runcl')

# callback function to process the result
def result_callback(result):
    logger.info("=" * 60)
    logger.info("CALLBACK: Result received from server!")
    logger.info(f"Result list: {result.value}")
    logger.info("=" * 60)
    print("\nResult: {}".format(result.value))

cl = rpc.Client()
cl.run()
# create initial list
base_list = rpc.DBList({'foo'})

# make asynchronous RPC call with callback
logger.info("Making asynchronous RPC call...")
cl.append('bar', base_list, callback=result_callback)

# simulate that client continues to work while waiting for response
logger.info("Client continues to do other work while waiting for server response...")
for i in range(12):
    print(f"[Client] Doing other work... ({i+1}s)")
    time.sleep(1)

logger.info("Main client activity finished. Waiting for response thread...")

cl.stop()
logger.info("Client stopped.")


