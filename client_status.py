#!/usr/bin/env python3
"""
client_status.py - Student 2: Service status client (CHECK).

Sends a service name to the monitoring server and displays the returned status:
Responding, Connection refused, No response, or Unknown service.

Usage example:
    python client_status.py 127.0.0.1 9000 tcp-test
"""
import argparse
import sys

from protocol import ClientError, send_request, valid_port


def main():
    parser = argparse.ArgumentParser(description="Service status client (CHECK)")
    parser.add_argument("host", help="monitoring server address")
    parser.add_argument("port", type=valid_port, help="monitoring server port")
    parser.add_argument("service", help="name of the lab service to check")
    args = parser.parse_args()
    try:
        lines = send_request(args.host, args.port, "CHECK " + args.service, timeout=10)
    except ClientError as err:
        print("Error:", err)
        sys.exit(1)
    print("Service '%s': %s" % (args.service, lines[0][2:].strip()))


if __name__ == "__main__":
    main()
