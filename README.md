# Network Lab Service Monitor

University of Petra - Information & Network Security Programming (605346) - Semester 1, 2026-2027

## Team members
| Role | Name | Student ID |
|---|---|---|
| Student 1 - Server (`server.py`) | Iyad Nader Ahmad Al-Saadi | 202211140_IS |
| Student 2 - Service status client (`client_status.py`) | Ahmad Rizq Dheeb Ali | 202210826_IS |
| Student 3 - Service response time client (`client_response_time.py`) | Saeed Salah Mohammad Jumaa Hamed | 202210117_IS |
| Student 4 - Monitoring history client (`client_history.py`) | Sarah Emad Mohammad Nabil Al-Beera | 202310119_IS |

## Files
| File | Purpose |
|---|---|
| `server.py` | Multi-threaded monitoring server (CHECK, MEASURE, HISTORY) with thread-safe logging |
| `client_status.py` | CHECK client |
| `client_response_time.py` | MEASURE client |
| `client_history.py` | HISTORY client |
| `protocol.py` | Shared protocol description, validation and request helper |
| `lab_services.py` | Local TCP test service / UDP echo service for the demonstration |
| `requirements.txt` | No external dependencies |

## Setup
Python 3.8+ only. No packages to install.

## Example commands (one terminal per command)
```
# 1. Start two test services on localhost
python lab_services.py tcp 9101
python lab_services.py udp 9102

# 2. Start the monitoring server
#    (defaults: tcp-test = 127.0.0.1:9101/tcp, udp-echo = 127.0.0.1:9102/udp)
python server.py --port 9000
#    custom services: python server.py --port 9000 --service web:127.0.0.1:9101:tcp --service dns:127.0.0.1:9102:udp

# 3. Run the clients
python client_status.py 127.0.0.1 9000 tcp-test
python client_response_time.py 127.0.0.1 9000 tcp-test 5
python client_history.py 127.0.0.1 9000
python client_history.py 127.0.0.1 9000 --service tcp-test

# 4. Stop the TCP test service (Ctrl+C) and repeat step 3 to see the change
```

## Expected output
```
$ python client_status.py 127.0.0.1 9000 tcp-test
Service 'tcp-test': Responding

$ python client_response_time.py 127.0.0.1 9000 tcp-test 3
Response times for 'tcp-test':
  Attempt 1: 0.149 ms   Responding
  Attempt 2: 0.044 ms   Responding
  Attempt 3: 0.025 ms   Responding
Successful attempts: 3 / 3
Timeouts: 0
Other failures: 0

$ python client_history.py 127.0.0.1 9000 --service tcp-test
Timestamp            Service        Outcome
----------------------------------------------------
2026-11-21 15:34:47  tcp-test       Responding
2026-11-21 15:34:48  tcp-test       Connection refused     <- after the service was stopped
```
Possible CHECK statuses: `Responding`, `Connection refused`, `No response`, `Host resolution error`, `Unknown service`.

## Design decisions
- **TCP** between clients and server; one request per connection, so no message framing is needed.
- **Text protocol** (documented in `protocol.py`): `CHECK <service>`, `MEASURE <service> <attempts>`, `HISTORY [service]`. The first response line is `OK ...` or `ERROR <message>`.
- **Approved services only**: the server checks only the services given with `--service` (testing is limited to localhost / authorized lab systems).
- **Timeouts**: each service check waits at most 2 seconds; MEASURE accepts 1-20 attempts.
- A TCP check succeeds when a connection is established; a UDP check succeeds when a probe gets a reply (an ICMP "port unreachable" is reported as `Connection refused`).
- **Exception handling**: invalid ports, hostname resolution errors, timeouts, refused connections, bad requests and log-file errors all produce clear messages.

## How the server handles concurrent requests and logs safely
- The main thread only calls `accept()`. Each accepted connection gets its own `threading.Thread` (`handle_client`), so the clients are served at the same time and a slow check (e.g. a timeout) never blocks the others.
- Shared data is protected with locks: the history list by a `threading.Lock` inside the `History` class, and the log file by a `threading.Lock` inside the `Logger` class.
- `Logger.write()` builds the complete line first, then writes and flushes it while holding the lock, so entries from different threads never interleave or overwrite each other. Each run creates `logs/monitor_YYYYmmdd_HHMMSS.log`; every line has a timestamp, the client address, the request and the outcome.
- Tested with 40 simultaneous clients: all 40 entries were logged completely.
