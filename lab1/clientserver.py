"""
Client and server using classes
"""

import logging
import socket
import struct

import const_cs
from context import lab_logging

from tel import tel


lab_logging.setup(stream_level=logging.INFO)  # init loging channels for the lab

# pylint: disable=logging-not-lazy, line-too-long


def recv_all(connection: socket.socket, n: int) -> bytes | None:
    """Helper function to reliably receive exactly n bytes."""
    data: bytes = b''
    while len(data) < n:
        bytes_needed = n - len(data)
        chunk = connection.recv(bytes_needed)
        if not chunk:
            return None
        data += chunk
    return data


class Server:
    """ The server """
    _logger = logging.getLogger("vs2lab.lab1.clientserver.Server")
    _serving = True

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # prevents errors due to "addresses in use"
        self.sock.bind((const_cs.HOST, const_cs.PORT))
        self.sock.settimeout(3)  # time out in order not to block forever
        self._logger.info("Server bound to socket %s", self.sock)

    def get_tel(self, name: str) -> str | None:
        self._logger.info('getting number for: %s', name)
        return tel.get(name)

    def format_get_result(self, number: str | None) -> str:
        self._logger.info('formatting result')
        command: str = ''
        msg: str = '\n'
        if not number:
            command = 'NOT_FOUND'
            msg = ''
        else:
            command = 'FOUND'
            msg = msg + number

        return command + msg

    def getall_tel(self) -> list[tuple[str, str]]:
        return list(tel.items())

    def format_getall_result(self, numbers: list[tuple[str, str]]) -> str:
        self._logger.info('formatting result')
        command: str = 'ENTRIES'

        numbers_str = [f"{name}: {number}" for name, number in numbers]
        msg = '\n' + ';'.join(numbers_str)

        return command + msg

    def serve(self):
        """ Serve echo """
        print(tel.items())
        self.sock.listen(1)

        while self._serving:  # as long as _serving (checked after connections or socket timeouts)
            try:
                (connection, _) = self.sock.accept()  # returns new socket and address of client
                while True:  # forever
                    len_prefix: bytes | None = recv_all(connection, 4)  # read length prefix first
                    if not len_prefix:
                        self._logger.info("Connection closed by client.")
                        break
                    self._logger.info("Received message length prefix, unpacking ...")
                    (msg_len,) = struct.unpack('!I', len_prefix)
                    self._logger.info(f"Message length is: {msg_len} bytes. Now receiving full message ...")
                    data_bytes = recv_all(connection, msg_len)
                    if not data_bytes:
                        self._logger.error("Connection closed unexpectedly while receiving message body.")
                        break
                    data = data_bytes.decode('ascii')
                    self._logger.info("Message received: %r", data)
                    data_lines = data.splitlines()
                    command = data_lines[0]
                    self._logger.info("Command: %s", command)

                    # Determine response message
                    formatted_msg: str
                    if command == 'GET':
                        if len(data_lines) < 2:
                            self._logger.warning("Malformed GET command received (missing parameter).")
                            formatted_msg = 'ERR\nMalformed GET command'
                        else:
                            query_param: str = data_lines[1]
                            tel_result = self.get_tel(query_param)
                            formatted_msg = self.format_get_result(tel_result)
                    elif command == 'GETALL':
                        tel_result = self.getall_tel()
                        formatted_msg = self.format_getall_result(tel_result)
                    else:
                        self._logger.warning("Command %s not supported", command)
                        formatted_msg = 'ERR\nCommand not supported'
                    
                    # Encode message and prepend length prefix before sending
                    msg_bytes_out = formatted_msg.encode('ascii')
                    len_prefix_out = struct.pack('!I', len(msg_bytes_out))
                    full_message_out = len_prefix_out + msg_bytes_out
                    
                    self._logger.info("Sending message with length %d", len(msg_bytes_out))
                    connection.sendall(full_message_out)

                connection.close()  # close the connection
            except socket.timeout:
                pass  # ignore timeouts
        self.sock.close()
        self._logger.info("Server down.")


class Client:
    """ The client """
    logger = logging.getLogger("vs2lab.a1_layers.clientserver.Client")

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((const_cs.HOST, const_cs.PORT))
        self.logger.info("Client connected to socket %s", self.sock)

    def call(self, msg_in: str = "GETALL"):
        """ Call server """

        # Encode message and prepend length prefix
        msg_bytes = msg_in.encode('ascii')
        msg_len = len(msg_bytes)
        self.logger.info("Msg length %r", msg_len)
        len_prefix = struct.pack('!I', msg_len)  # creates a 4-byte unsigned integer
        full_message = len_prefix + msg_bytes

        self.logger.info("Sending message: %r", full_message)
        self.sock.sendall(full_message)  # sendall repeatedly tries to send until all data is sent

        # Receive response: first get length prefix, then the message body
        len_prefix_in = recv_all(self.sock, 4)
        if not len_prefix_in:
            print("Server closed connection unexpectedly.")
            return "ERR"
        
        (msg_len_in,) = struct.unpack('!I', len_prefix_in)
        self.logger.info("Expecting %d bytes from server.", msg_len_in)

        data_bytes = recv_all(self.sock, msg_len_in)
        if not data_bytes:
            print("Server closed connection while sending message body.")
            return "ERR"

        self.logger.info("Message received: %r", data_bytes.decode('ascii'))
        data = data_bytes.decode('ascii')
        data_lines = data.splitlines()

        command = data_lines[0]
        self.logger.info("Command: %s", command)
        msg: str = ''
        if command == 'FOUND':
            msg = data_lines[1]
        elif command == 'NOT_FOUND':
            msg = 'Person not in dictionary'
        elif command == 'ENTRIES':
            msg = '\n'.join(data_lines[1].split(';'))
        elif command == 'ERR':
            msg = data_lines[1]
        else:
            msg = 'Weird response from server'
            self.logger.warning("Command %s not supported", command)

        self.sock.close()  # close the connection
        self.logger.info("Client down.")
        return msg

    def send_get(self, name: str):
        self.call('GET\n' + name)

    def send_getall(self):
        self.call('GETALL')

    def close(self):
        """ Close socket """
        self.sock.close()