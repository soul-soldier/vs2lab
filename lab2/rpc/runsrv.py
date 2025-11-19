import logging

import rpc
from context import lab_channel, lab_logging

lab_logging.setup(stream_level=logging.INFO)
logger = logging.getLogger('vs2lab.lab2.rpc.runsrv')

chan = lab_channel.Channel()
chan.channel.flushall()
logger.debug('Flushed all redis keys.')

# added logging for threading
logger.info('Starting asynchronous RPC server...')
logger.info('Server will acknowledge requests immediately and process them asynchronously.')

srv = rpc.Server()
srv.run()

