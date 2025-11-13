"""
Unit tests for the client-server phonebook service.
"""

import logging
import threading
import time
import unittest

import clientserver
from context import lab_logging
from tel import tel  # Import the phone book to verify results

lab_logging.setup(stream_level=logging.INFO)


class TestTelService(unittest.TestCase):
    """Test suite for the phonebook Client and Server."""
    _server = clientserver.Server()
    _server_thread = threading.Thread(target=_server.serve)

    @classmethod
    def setUpClass(cls):
        """Starts the server in a background thread once before all tests."""
        cls._server_thread.start()
        time.sleep(0.2)

    def setUp(self):
        """Creates a new client instance for each test to ensure isolation."""
        super().setUp()
        self.client = clientserver.Client()

    def test_get_found(self):
        """Tests the GET command for a name that exists in the phonebook."""
        response = self.client.call("GET\njack")
        self.assertEqual(response, '4098')

    def test_get_not_found(self):
        """Tests the GET command for a name that does not exist."""
        response = self.client.call("GET\nnonexistent_user")
        self.assertEqual(response, 'Person not in dictionary')

    def test_getall_and_large_message(self):
        """
        Tests the GETALL command and verifies that messages larger than
        1024 bytes are handled correctly.
        """
        response = self.client.call("GETALL")
        returned_entries = response.split('\n')

        print("First 10 entries received:\n", "\n".join(returned_entries[:10]))

        # Verify the response is not an error message
        self.assertNotIn(response, ['Person not in dictionary', 'Weird response from server', 'Command not supported'])

        # Check for a couple of known entries in the response
        self.assertIn('jack: 4098', response)
        self.assertIn('sape: 4139', response)

        # The most important check: verify that all entries are returned.
        self.assertEqual(len(returned_entries), len(tel))

        # Explicitly check that the received message size is greater than 1024 bytes,
        # confirming the system's ability to handle large data transfers.
        self.assertGreater(len(response.encode('ascii')), 1024, "Response payload should be larger than 1024 bytes")

    def test_unknown_command(self):
        """Tests the server's response to an unsupported command."""
        response = self.client.call("DELETE\njack")
        self.assertEqual(response, 'Command not supported')

    def test_malformed_get_command(self):
        """
        Tests a malformed GET command (missing the name parameter).
        The server should close the connection, and the client should handle it.
        """
        response = self.client.call("GET")
        # When the server encounters an error processing the request, it closes the
        # connection. The client's call() method is expected to detect this
        # and return its designated error string.
        self.assertEqual(response, "Malformed GET command")

    def tearDown(self):
        """Closes the client socket after each test."""
        self.client.close()

    @classmethod
    def tearDownClass(cls):
        """Stops the server thread after all tests have run."""
        # Set the serving flag to False to break the server's main loop
        cls._server._serving = False  # pylint: disable=protected-access
        # Wait for the server thread to terminate cleanly
        cls._server_thread.join()


if __name__ == '__main__':
    unittest.main()