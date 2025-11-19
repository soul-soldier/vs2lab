import constRPC
import threading
import time
import logging

from context import lab_channel


class DBList:
    def __init__(self, basic_list):
        self.value = list(basic_list)

    def append(self, data):
        self.value = self.value + [data]
        return self


class Client:
    def __init__(self):
        self.chan = lab_channel.Channel()
        self.client = self.chan.join('client')
        self.server = None
        # added logging + response thread
        self.logger = logging.getLogger('vs2lab.lab2.rpc.Client')
        self.response_thread = None

    def run(self):
        self.chan.bind(self.client)
        self.server = self.chan.subgroup('server')

    def stop(self):
        # wait for response thread to complete if it exists
        if self.response_thread is not None and self.response_thread.is_alive():
            self.logger.info("Waiting for response thread to complete...")
            self.response_thread.join(timeout=15)
        self.chan.leave('client')
    
    def append(self, data, db_list, callback=None):
        # asynchronous rcp call to server's append method
        assert isinstance(db_list, DBList)
        msglst = (constRPC.APPEND, data, db_list)  # message payload
        self.chan.send_to(self.server, msglst)  # send msg to server

        # added non-blockiing wait for response with background thread
        if callback is not None:
            self.response_thread = threading.Thread(
                target=self._wait_for_response,
                args=(callback,)
            )
            self.response_thread.daemon = False
            self.response_thread.start()
    
    def _wait_for_response(self, callback):
        # client method to wait for server response in background thread
        try:
            while True:
                msgrcv = self.chan.receive_from(self.server)
                response = msgrcv[1]
                
                # check if this is an ACK or result
                if isinstance(response, tuple) and len(response) == 2 and response[0] == 'ACK':
                    self.logger.info("Received ACK from server, waiting for actual result...")
                    continue  # wait for actual result
                
                self.logger.info("Received final response from server")
                # Call the callback function with the result
                callback(response)
                break
        except Exception as e:
            self.logger.error(f"Error waiting for response: {e}")


class Server:
    def __init__(self):
        self.chan = lab_channel.Channel()
        self.server = self.chan.join('server')
        self.timeout = 3
        # added logging
        self.logger = logging.getLogger('vs2lab.lab2.rpc.Server')

    @staticmethod
    def append(data, db_list):
        assert isinstance(db_list, DBList)  # - Make sure we have a list
        return db_list.append(data)

    def run(self):
        self.chan.bind(self.server)
        while True:
            msgreq = self.chan.receive_from_any(self.timeout)  # wait for any request
            if msgreq is not None:
                client = msgreq[0]  # see who is the caller
                msgrpc = msgreq[1]  # fetch call & parameters
                if constRPC.APPEND == msgrpc[0]:  # check what is being requested

                    # server sends ACK
                    self.chan.send_to({client}, ('ACK', None))
                    self.logger.info(f"Sent ACK to client {client}")
                    
                    # process the request in a separate thread to simulate long-running operation
                    processing_thread = threading.Thread(
                        target=self._process_request,
                        args=(client, msgrpc)
                    )
                    processing_thread.daemon = True
                    processing_thread.start()
                else:
                    pass  # unsupported request, simply ignore

    # process request in background: pause 10 seconds then send result
    # client -> client id for response
    # msgrpc -> the rpc message
    def _process_request(self, client, msgrpc):
        try:
            self.logger.info(f"Processing request from client {client}")
            # simulate long processing
            time.sleep(10)
            
            # do the actual work
            result = self.append(msgrpc[1], msgrpc[2])  # local call
            self.logger.info(f"Processing complete, sending result to client {client}")
            self.chan.send_to({client}, result)
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
