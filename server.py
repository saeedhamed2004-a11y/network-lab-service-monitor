#!/usr/bin/env python3
"""
server.py - Student 1: Network Lab Service Monitor server (TCP, multi-threaded).

Handles CHECK, MEASURE and HISTORY requests from the three clients. Only the
approved lab services (name:host:port:protocol) can be checked. Every request
and its outcome is written to a timestamped log file in a thread-safe way.

Usage example:
    python server.py --port 9000
    python server.py --port 9000 --service web:127.0.0.1:9101:tcp --service echo:127.0.0.1:9102:udp
"""
import argparse
import os
import socket
import sys
import threading
import time
from collections import deque
from datetime import datetime

from protocol import (ENCODING, MAX_ATTEMPTS, MAX_LINE, CHECK_TIMEOUT, valid_port)

DEFAULT_SERVICES = ["tcp-test:127.0.0.1:9101:tcp", "udp-echo:127.0.0.1:9102:udp"]
HISTORY_LIMIT = 20       # records returned by HISTORY
HISTORY_STORE = 1000     # records kept in memory


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Logger:
    """Thread-safe log writer: a lock guarantees entries never interleave."""

    def __init__(self, log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
            name = "monitor_%s.log" % datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = os.path.join(log_dir, name)
            self._file = open(self.path, "a", encoding="utf-8")
        except OSError as err:
            raise SystemExit("Error: cannot create log file in '%s': %s" % (log_dir, err))
        self._lock = threading.Lock()

    def write(self, message):
        line = "[%s] %s\n" % (now(), message)
        with self._lock:
            try:
                self._file.write(line)
                self._file.flush()
            except OSError as err:          # keep serving even if the disk fails
                print("Log write error:", err, file=sys.stderr)

    def close(self):
        with self._lock:
            self._file.close()


class History:
    """Thread-safe store of recent check results."""

    def __init__(self):
        self._records = deque(maxlen=HISTORY_STORE)
        self._lock = threading.Lock()

    def add(self, service, outcome):
        with self._lock:
            self._records.append((now(), service, outcome))

    def recent(self, service=None):
        with self._lock:
            records = list(self._records)
        if service:
            records = [r for r in records if r[1] == service]
        return records[-HISTORY_LIMIT:]


def parse_service(text):
    """Parse 'name:host:port:protocol' into a dict; raise ValueError if invalid."""
    parts = text.split(":")
    if len(parts) != 4:
        raise ValueError("service '%s' must look like name:host:port:protocol" % text)
    name, host, port, proto = parts
    proto = proto.lower()
    if not name or not host:
        raise ValueError("service '%s' has an empty name or host" % text)
    if proto not in ("tcp", "udp"):
        raise ValueError("service '%s': protocol must be tcp or udp" % text)
    try:
        port = valid_port(port)
    except argparse.ArgumentTypeError as err:
        raise ValueError("service '%s': %s" % (text, err))
    return {"name": name, "host": host, "port": port, "proto": proto}


def check_service(svc, timeout=CHECK_TIMEOUT):
    """
    Perform one check of a lab service.
    Returns (status, elapsed_ms). elapsed_ms is the TCP connection time or the
    UDP reply time for a successful check, otherwise None.
    """
    start = time.perf_counter()
    try:
        if svc["proto"] == "tcp":
            sock = socket.create_connection((svc["host"], svc["port"]), timeout=timeout)
            sock.close()
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.settimeout(timeout)
                sock.connect((svc["host"], svc["port"]))
                sock.send(b"PING")
                sock.recv(1024)
            finally:
                sock.close()
    except socket.gaierror:
        return "Host resolution error", None
    except (ConnectionRefusedError, ConnectionResetError):
        return "Connection refused", None
    except socket.timeout:
        return "No response", None
    except OSError as err:
        return "Error (%s)" % err.strerror, None
    return "Responding", (time.perf_counter() - start) * 1000.0


class MonitorServer:
    def __init__(self, host, port, services, log_dir):
        self.host, self.port = host, port
        self.services = {s["name"]: s for s in services}
        self.logger = Logger(log_dir)
        self.history = History()
        self.sock = None

    # ---------- request handlers ----------
    def do_check(self, args):
        if len(args) != 1:
            return ["ERROR Usage: CHECK <service>"], "bad request"
        name = args[0]
        svc = self.services.get(name)
        if svc is None:
            self.history.add(name, "Unknown service")
            return ["OK Unknown service"], "CHECK %s -> Unknown service" % name
        status, _ = check_service(svc)
        self.history.add(name, status)
        return ["OK " + status], "CHECK %s -> %s" % (name, status)

    def do_measure(self, args):
        if len(args) != 2 or not args[1].isdigit():
            return ["ERROR Usage: MEASURE <service> <attempts>"], "bad request"
        name, attempts = args[0], int(args[1])
        if not 1 <= attempts <= MAX_ATTEMPTS:
            return ["ERROR attempts must be between 1 and %d" % MAX_ATTEMPTS], "bad request"
        svc = self.services.get(name)
        if svc is None:
            self.history.add(name, "Unknown service")
            return ["ERROR Unknown service: " + name], "MEASURE %s -> Unknown service" % name
        lines, ok, timeouts, other = ["OK"], 0, 0, 0
        for i in range(1, attempts + 1):
            status, ms = check_service(svc)
            self.history.add(name, status)
            if status == "Responding":
                ok += 1
            elif status == "No response":
                timeouts += 1
            else:
                other += 1
            lines.append("ATTEMPT %d %s %s" % (i, "%.3f" % ms if ms is not None else "-", status))
        lines.append("SUMMARY attempts=%d successful=%d timeouts=%d other_failures=%d"
                     % (attempts, ok, timeouts, other))
        return lines, "MEASURE %s x%d -> successful=%d timeouts=%d other=%d" % (name, attempts, ok, timeouts, other)

    def do_history(self, args):
        if len(args) > 1:
            return ["ERROR Usage: HISTORY [service]"], "bad request"
        records = self.history.recent(args[0] if args else None)
        lines = ["OK %d" % len(records)] + ["%s|%s|%s" % r for r in records]
        return lines, "HISTORY %s -> %d records" % (args[0] if args else "(all)", len(records))

    # ---------- connection handling ----------
    def handle_client(self, conn, addr):
        who = "%s:%d" % addr
        try:
            conn.settimeout(10)
            data = b""
            while b"\n" not in data and len(data) < MAX_LINE:
                chunk = conn.recv(MAX_LINE)
                if not chunk:
                    break
                data += chunk
            request = data.decode(ENCODING, errors="replace").strip()
            parts = request.split()
            if not parts:
                lines, outcome = ["ERROR Empty request"], "bad request"
            else:
                handler = {"CHECK": self.do_check, "MEASURE": self.do_measure,
                           "HISTORY": self.do_history}.get(parts[0].upper())
                if handler is None:
                    lines, outcome = ["ERROR Unknown command: " + parts[0]], "bad request"
                else:
                    lines, outcome = handler(parts[1:])
            conn.sendall(("\n".join(lines) + "\n").encode(ENCODING))
            self.logger.write("%s | request='%s' | outcome=%s" % (who, request, outcome))
        except OSError as err:
            self.logger.write("%s | connection error: %s" % (who, err))
        finally:
            conn.close()

    def serve(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.host, self.port))
        except OSError as err:
            raise SystemExit("Error: cannot bind to %s:%d: %s" % (self.host, self.port, err))
        self.sock.listen(10)
        print("[*] Monitoring server listening on %s:%d" % (self.host, self.port))
        print("[*] Approved services:")
        for s in self.services.values():
            print("    %-12s %s:%d (%s)" % (s["name"], s["host"], s["port"], s["proto"]))
        print("[*] Log file:", self.logger.path)
        self.logger.write("server started on %s:%d" % (self.host, self.port))
        try:
            while True:
                conn, addr = self.sock.accept()
                # one worker thread per client connection
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[*] Shutting down")
        finally:
            self.sock.close()
            self.logger.write("server stopped")
            self.logger.close()


def main():
    parser = argparse.ArgumentParser(description="Network Lab Service Monitor server")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    parser.add_argument("--port", type=valid_port, default=9000, help="port to listen on (default 9000)")
    parser.add_argument("--service", action="append", metavar="NAME:HOST:PORT:PROTO",
                        help="approved lab service (repeatable). Default: %s" % ", ".join(DEFAULT_SERVICES))
    parser.add_argument("--log-dir", default="logs", help="log directory (default ./logs)")
    args = parser.parse_args()
    try:
        services = [parse_service(s) for s in (args.service or DEFAULT_SERVICES)]
    except ValueError as err:
        parser.error(str(err))
    MonitorServer(args.host, args.port, services, args.log_dir).serve()


if __name__ == "__main__":
    main()
