#!/usr/bin/env python3
"""
lab_services.py - Local test service for the demonstration (localhost only).

Starts either a TCP test server or a UDP echo service. Stop it with Ctrl+C to
show how the monitoring server reports the change.

Usage examples:
    python lab_services.py tcp 9101
    python lab_services.py udp 9102
"""
import argparse
import socket
import threading

from protocol import valid_port


def run_tcp(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(5)
    print("TCP test service listening on 127.0.0.1:%d (Ctrl+C to stop)" % port)
    try:
        while True:
            conn, _ = srv.accept()
            conn.close()
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


def run_udp(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", port))
    print("UDP echo service listening on 127.0.0.1:%d (Ctrl+C to stop)" % port)
    try:
        while True:
            data, addr = srv.recvfrom(1024)
            srv.sendto(data, addr)
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


def main():
    parser = argparse.ArgumentParser(description="Local lab test service")
    parser.add_argument("protocol", choices=["tcp", "udp"])
    parser.add_argument("port", type=valid_port)
    args = parser.parse_args()
    try:
        (run_tcp if args.protocol == "tcp" else run_udp)(args.port)
    except OSError as err:
        raise SystemExit("Error: cannot start service on port %d: %s" % (args.port, err))


if __name__ == "__main__":
    main()
