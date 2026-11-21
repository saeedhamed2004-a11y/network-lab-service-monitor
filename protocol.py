"""
protocol.py - Shared protocol helpers used by the server and the three clients.

Agreed team protocol (TCP, text based, one request per connection, UTF-8):

  Request  (one line, ends with "\\n"):
      CHECK <service>
      MEASURE <service> <attempts>
      HISTORY [service]

  Response (lines; the server closes the connection when finished):
      First line : "OK ..." or "ERROR <message>"
      CHECK      : OK <status>
                   status = Responding | Connection refused | No response |
                            Host resolution error | Unknown service
      MEASURE    : OK
                   ATTEMPT <n> <time_ms or -> <status>      (one per attempt)
                   SUMMARY attempts=<a> successful=<s> timeouts=<t> other_failures=<f>
      HISTORY    : OK <count>
                   <timestamp>|<service>|<outcome>          (one per record)
"""
import argparse
import socket

ENCODING = "utf-8"
MAX_LINE = 1024          # maximum request size in bytes
MAX_ATTEMPTS = 20        # maximum MEASURE attempts accepted by the server
CHECK_TIMEOUT = 2.0      # seconds the server waits for a lab service


class ClientError(Exception):
    """Raised when the client cannot get a valid response from the server."""


def valid_port(text):
    """argparse type: accept only integers in 1..65535."""
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid port '%s': must be an integer" % text)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("invalid port %d: must be between 1 and 65535" % port)
    return port


def positive_int(text):
    """argparse type: accept only integers >= 1."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid number '%s': must be an integer" % text)
    if value < 1:
        raise argparse.ArgumentTypeError("invalid number %d: must be at least 1" % value)
    return value


def send_request(host, port, request, timeout):
    """
    Send one request line to the monitoring server and return the response
    as a list of lines. Raises ClientError with a clear message on failure.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((request + "\n").encode(ENCODING))
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
    except socket.gaierror as err:
        raise ClientError("Cannot resolve host '%s': %s" % (host, err))
    except ConnectionRefusedError:
        raise ClientError("Connection refused: no server is listening on %s:%d" % (host, port))
    except socket.timeout:
        raise ClientError("Timed out while talking to the server %s:%d" % (host, port))
    except OSError as err:
        raise ClientError("Network error: %s" % err)

    text = b"".join(chunks).decode(ENCODING, errors="replace")
    lines = text.splitlines()
    if not lines:
        raise ClientError("Empty response from the server")
    if lines[0].startswith("ERROR"):
        raise ClientError("Server error: " + lines[0][5:].strip())
    return lines
