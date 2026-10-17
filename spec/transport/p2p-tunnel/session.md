# P2P tunnel: session lifetime, timers, errors and optional paths

Part of the [P2P tunnel chapter](index.md). This file covers how a tunnel session ends,
every tunnel-layer timer, limits and malformed input, the local API error codes (as distinct
from the few results carried on the wire), and the optional LAN-direct and attached-session
paths. Frames are in [framing.md](framing.md), channels in [channels.md](channels.md).

Basis: static analysis of the app tunnel library and Java binding (app 3.3.2) and firmware
9.31 (both builds).

## Teardown

R54. There is no tunnel logout opcode. A session ends when RDT or IOTC ends. READ.

R55. Agent disconnect: mark the session unused, destroy RDT (abort uses RDT abort instead),
release every channel, reset bookkeeping, join the workers, and close IOTC if the tunnel owns
it. Attached sessions leave the caller's IOTC session open. READ. Release sends no frames
(R46), so the peer learns of the end from RDT/IOTC, not from tunnel CLOSE frames.

R56. When IOTC reports the session lost, a worker sets the session stop flag and calls the
tunnel status callback with -30006 (`TUNNEL_ER_DISCONNECTED`); the read loops exit and the
socket reader releases the channels. READ.

R57. Server session exit: abort RDT, sleep 1 s, close the owned IOTC session, sleep 1 s.
READ.

R58. RDT write failures. READ:

- SETUP write fails: close the accepted local socket; the channel is not activated.
- DATA write fails: keep the frame and retry (R41).
- END or CLOSE write fails in the socket reader: release that channel and mark the session
  unused, which releases all its channels.
- A negative RDT status in the reader's main loop ends the session the same way.
- LOGIN and verification responses are not retried. PAUSE/RESUME bookkeeping changes even on
  failure (R48).

## Timers and limits

These are local scheduling values. None is sent on the wire, and there is no tunnel-level
retransmission timer. READ.

| Operation | Value / rule |
|---|---|
| RDT creation, both roles | 30000 ms |
| Agent wait for login result | 30000 ms, single read |
| Server wait for LOGIN | 90000 ms, single read |
| Established RDT read | 100 ms per read, retried while active |
| Port / service verification | 5000 ms (LAN-direct: 1000 ms); poll 100 ms; no retransmission |
| Local listener `select` | 500 ms |
| No free channel | sleep 500 ms, rescan, no cap |
| Socket-read `select` | 100 ms; 100 ms sleep if nothing eligible |
| Socket-queue sender | 100 ms timed wait, also event-driven |
| Channel reuse quarantine | 1 s sweeps; free after state exceeds 30 (about 28-29 s, INFERRED) |
| Unknown established opcode | 100 ms sleep |
| RDT send-queue congestion | 5 ms (modes 0/1) or 10 ms (mode 2), recheck |
| Server IOTC listen resource error -18 | sleep 2 s |
| Server stop / deinitialize | 1 s sleeps |

R59. The Server's per-channel TCP connect is blocking with no tunnel timeout. There is no
idle timer on established channels (a last-I/O timestamp is kept but not enforced). Liveness
comes from IOTC/RDT. READ.

| Limit | Value |
|---|---|
| DATA payload sent | at most 8192 bytes |
| Native established receive buffer | 8196 bytes (not checked against `L`) |
| Channel indices per session | 256 (8-bit) |
| Mapping table | 256 entries |
| Legacy LOGIN data | 0-1000 bytes accepted by the API; Server reads at most 1004 bytes in total |
| Service ID | 32 bytes plus NUL |

All READ.

R60. A new implementation SHOULD reject incomplete or malformed control payloads, service IDs
with no NUL inside their field, oversized DATA and inconsistent legacy lengths, and SHOULD
bound queues and close stalled channels by an explicit local policy. INFERRED. The native
code defines no safe behaviour for malformed frames; these are policy choices, not wire
requirements.

## API errors versus wire results

R61. The tunnel API returns local codes; they never appear on the wire. The only wire fields
that carry a result are the LOGIN result (signed 32-bit, [LOGIN_PASS / LOGIN_REJECT (`08` / `09`, Server -> Agent)](framing.md#login_pass--login_reject-08--09-server---agent) of
[framing.md](framing.md)), the verification validity bytes and the one-byte DATA_CLOSE result
(1 or 2). READ.

Named codes from the app's Java binding. READ.

| Code | Name | Code | Name |
|---:|---|---:|---|
| 0 | `TUNNEL_ER_NoERROR` | -30018 | `TUNNEL_ER_LOGIN_FAILED` |
| -30000 | `TUNNEL_ER_NOT_INITIALIZED` | -30019 | `TUNNEL_ER_EXCEED_MAX_SESSION` |
| -30001 | `TUNNEL_ER_EXCEED_MAX_SERVICE` | -30020 | `TUNNEL_ER_AGENT_NOT_SUPPORT` |
| -30002 | `TUNNEL_ER_BIND_LOCAL_SERVICE` | -30021 | `TUNNEL_ER_INVALID_ARG` |
| -30003 | `TUNNEL_ER_LISTEN_LOCAL_SERVICE` | -30022 | `TUNNEL_ER_OS_RESOURCE_LACK` |
| -30004 | `TUNNEL_ER_FAIL_CREATE_THREAD` | -30023 | `TUNNEL_ER_AGENT_NOT_CONNECTING` |
| -30005 | `TUNNEL_ER_ALREADY_CONNECTED` | -30024 | `TUNNEL_ER_NO_FREE_SESSION` |
| -30006 | `TUNNEL_ER_DISCONNECTED` | -30025 | `TUNNEL_ER_CONNECTION_CANCELLED` |
| -30007 | `TUNNEL_ER_ALREADY_INITIALIZED` | -30026 | `TUNNEL_ER_OPERATION_IS_INVALID` |
| -30008 | `TUNNEL_ER_AUTH_FAILED` | -30027 | `TUNNEL_ER_HANDSHAKE_FAILED` |
| -30009 | `TUNNEL_ER_EXCEED_MAX_LEN` | -30028 | `TUNNEL_ER_REMOTE_NOT_SUPPORT_DTLS` |
| -30010 | `TUNNEL_ER_INVALID_SID` | -30029 | `TUNNEL_ER_LOCAL_NOT_SUPPORT_DTLS` |
| -30011 | `TUNNEL_ER_UID_UNLICENSE` | -30030 | `TUNNEL_ER_TIMEOUT` |
| -30012 | `TUNNEL_ER_UID_NO_PERMISSION` | -30031 | `TUNNEL_ER_SESSION_CLOSE_BY_REMOTE` |
| -30013 | `TUNNEL_ER_UID_NOT_SUPPORT_RELAY` | -30032 | `TUNNEL_ER_REMOTE_TIMEOUT_DISCONNECT` |
| -30014 | `TUNNEL_ER_DEVICE_NOT_ONLINE` | -30033 | `TUNNEL_ER_REJECT` |
| -30015 | `TUNNEL_ER_DEVICE_NOT_LISTENING` | -30034 | `TUNNEL_ER_RETRY` |
| -30016 | `TUNNEL_ER_NETWORK_UNREACHABLE` | -30035 | `TUNNEL_ER_INIT_OTHER_MODULE_FAIL` |
| -30017 | `TUNNEL_ER_FAILED_SETUP_CONNECTION` | -30036 | `TUNNEL_ER_REMOTE_NOT_SUPPORT` |
| | | -31000 | `TUNNEL_ER_UNDEFINED` |

Note that the verification paths reuse some names loosely: a mismatched returned port gives
-30027 (`HANDSHAKE_FAILED`) and a verification write failure -30017 (R23). READ.

R62. RDT/IOTC errors are translated as below; other values pass through unchanged. Codes
-30037 to -30045 have no name in the Java binding. READ.

| RDT/IOTC | Tunnel | RDT/IOTC | Tunnel |
|---:|---:|---:|---:|
| -10024 | -30029 | -10008 | -30043 |
| -10023 | -30028 | -10007 | -30030 |
| -10021 | -30042 | -10006 | -30044 |
| -10016 | -30038 | -10004 | -30004 |
| -10015 | -30037 | -10003 | -30022 |
| -10012 | -30041 | -10002 | -30040 |
| -10010 | -30039 | -23 | -30032 |
| -10009 | -30045 | -22 | -30031 |

## Optional paths

### LAN-direct bypass

R63. Both sides enable it: the app initializes the tunnel agent with the direct flag set, and
the device initializes its tunnel server with it set (see [seestar-profile.md R69](seestar-profile.md#port-mapping-profile)).
The bypass follows full authentication: the client first builds the IOTC session, the RDT
channel and the tunnel LOGIN with credentials (30000 ms budget), and records the peer's IPv4
reported by IOTC only when the IOTC mode is LAN (mode 2). READ.

Per accepted connection on a local mapping listener, the Agent uses the bypass only if
the session is ready, direct is enabled locally, and the mapping is a port mapping (type 1). It
then verifies the port (1000 ms; retry only on -30034, up to 3 attempts, 500 ms apart) and
opens a second TCP socket straight to the peer's IOTC-reported IPv4 address and that port
(non-blocking connect, 1000 ms). On success it pumps bytes between the two sockets locally:
no SETUP, no DATA, no tunnel header. On socket or connect failure it falls back to SETUP; a
verification failure closes the accepted local socket. READ.

R64. The direct pump reads up to 8196 bytes per call, keeps unsent bytes, and uses a 1000 ms
select loop with a 100 ms idle sleep; the authenticated tunnel stays up for control. The app
decides on LAN-direct from its own configuration and IOTC mode, not from the login response
flag. READ. LAN-direct traffic is unencrypted. DOC (vendor integration guide). A client MAY
omit LAN-direct. INFERRED. Because the device classes such direct connections as external
rather than loopback, they need the 4700 verification exchange like any LAN client (see
[lan-discovery/app-scan.md: Control connection (summary)](../lan-discovery/app-scan.md#control-connection-summary)).
INFERRED. See [LAN discovery](../lan-discovery.md) for the plaintext LAN ports.

### Attached sessions and one tunnel per IOTC session

R65. The attach-connect and server-listen entry points run a tunnel over a caller-owned IOTC
session and channel (0-31), with the same LOGIN and frames; they add no opcodes. Normal
connect uses IOTC channel 0. READ.

R66. On firmware 9.31 the attached server mode is a process-global option that is off in the
shipped configuration; in that mode server-listen returns -30026 (after writing a slot flag,
so it is not a harmless probe). The device listener serves IOTC channel 0 only. READ.

R67. The tunnel keeps exactly one RDT handle, one 256-channel table and one worker set per
IOTC session (both firmware builds and the app). A client therefore cannot get a second,
independent tunnel by choosing another IOTC channel, another tunnel channel index or urgent
RDT data on the same session. To get independent tunnels it MUST open separate IOTC sessions,
as the app does (see [seestar-profile.md](seestar-profile.md#port-mapping-profile)).
READ (structure), INFERRED (consequence). Runtime behaviour is untested.
