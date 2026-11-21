#!/usr/bin/env python3
"""
client_response_time.py - Student 3: Service response time client (MEASURE).

Sends a service name and a number of attempts. Displays how long the server took
to establish a TCP connection or receive a UDP reply, and reports successful
attempts and timeouts.

Usage example:
    python client_response_time.py 127.0.0.1 9000 tcp-test 5
"""
import argparse
import sys

from protocol import CHECK_TIMEOUT, ClientError, positive_int, send_request, valid_port


def main():
    parser = argparse.ArgumentParser(description="Service response time client (MEASURE)")
    parser.add_argument("host", help="monitoring server address")
    parser.add_argument("port", type=valid_port, help="monitoring server port")
    parser.add_argument("service", help="name of the lab service to measure")
    parser.add_argument("attempts", type=positive_int, help="number of attempts")
    args = parser.parse_args()
    # allow enough time for every attempt to time out on the server side
    timeout = args.attempts * CHECK_TIMEOUT + 10
    try:
        lines = send_request(args.host, args.port,
                             "MEASURE %s %d" % (args.service, args.attempts), timeout=timeout)
    except ClientError as err:
        print("Error:", err)
        sys.exit(1)

    print("Response times for '%s':" % args.service)
    for line in lines[1:]:
        parts = line.split(" ", 3)
        if parts[0] == "ATTEMPT":
            _, number, ms, status = parts
            shown = "%s ms" % ms if ms != "-" else "-"
            print("  Attempt %s: %-10s %s" % (number, shown, status))
        elif parts[0] == "SUMMARY":
            values = dict(item.split("=") for item in line.split()[1:])
            print("Successful attempts: %s / %s" % (values["successful"], values["attempts"]))
            print("Timeouts: %s" % values["timeouts"])
            print("Other failures: %s" % values["other_failures"])


if __name__ == "__main__":
    main()
