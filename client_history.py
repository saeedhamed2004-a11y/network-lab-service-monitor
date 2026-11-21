#!/usr/bin/env python3
"""
client_history.py - Student 4: Monitoring history client (HISTORY).

Retrieves the recent checks and displays their timestamps, service names and
outcomes. The results can be filtered by service name.

Usage examples:
    python client_history.py 127.0.0.1 9000
    python client_history.py 127.0.0.1 9000 --service tcp-test
"""
import argparse
import sys

from protocol import ClientError, send_request, valid_port


def main():
    parser = argparse.ArgumentParser(description="Monitoring history client (HISTORY)")
    parser.add_argument("host", help="monitoring server address")
    parser.add_argument("port", type=valid_port, help="monitoring server port")
    parser.add_argument("--service", help="show only this service")
    args = parser.parse_args()
    request = "HISTORY" + (" " + args.service if args.service else "")
    try:
        lines = send_request(args.host, args.port, request, timeout=10)
    except ClientError as err:
        print("Error:", err)
        sys.exit(1)

    records = lines[1:]
    if not records:
        print("No checks recorded yet.")
        return
    print("%-20s %-14s %s" % ("Timestamp", "Service", "Outcome"))
    print("-" * 52)
    for record in records:
        timestamp, service, outcome = record.split("|", 2)
        print("%-20s %-14s %s" % (timestamp, service, outcome))


if __name__ == "__main__":
    main()
