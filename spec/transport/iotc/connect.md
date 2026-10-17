# IOTC connection establishment and NAT traversal

Part of [Kalay/IOTC session](index.md). This file specifies how a client finds servers, classifies
its NAT, races LAN, direct UDP, UDP relay and TCP relay paths, and the try-port traversal
generator. Packet layouts are in [framing.md](framing.md) (legacy) and
[rendezvous-gcm.md](rendezvous-gcm.md) (modern records). Established-session behaviour is in
[session.md](session.md). Labels and notation: [index: Conventions](index.md#conventions).

Basis: static analysis of the app library (app 3.3.2, the modern client) and the device library
(firmware 9.31, used as a cross-check of shared client code). State numbers below are local SDK
variables, never wire fields.

## Endpoint discovery

DOC. ThroughTek distinguishes master servers (authorize UIDs, point to P2P servers) from P2P
servers (register devices, assist direct or relayed connections). Modes are LAN, P2P and relay.

R1. Master host names are built from the licence (READ):

- If the licence has a `standalone` mapping for the region, use it.
- Otherwise the name is `<region>-<service>-<realm>` when the realm contains a dot, else that
  string plus a vendor platform domain suffix.
- Region starts as `all`. Service index 0 is `c-master`, 1 `d-master`, 2 `p2pod-master`.
- Service 2 and region `cn` use different vendor domain suffixes from the default. No Seestar
  condition that selects service 2 was found ([master-legacy: Master host names](../../auth/cloud-auth/master-legacy.md#master-host-names)).

The vendor domain suffixes are listed in
[embedded-constants.md: Master host-name suffixes](../../auth/cloud-auth/embedded-constants.md#master-host-name-suffixes).

R2. Ports (READ):

| Use | Port |
|---|---|
| LAN search socket (UDP, default; settable by API) | 32761 |
| Master, UDP | 10240 |
| Master and P2P server, TCP (cycled) | 80, 443, 21047, 8080, 8000 |

TCP ports 80 and 443 do not imply HTTP or HTTPS. READ. The app selects the master TCP port modulo
five; P2P-server TCP setup starts the cycle at a random index. READ. Do not substitute ports
reported for other Kalay products. INFERRED.

R3. LAN search broadcasts per interface netmask when no destination is given, and unicasts
otherwise. READ. See also [LAN discovery](../lan-discovery.md).

## NAT classification

R4. The NAT tracker keeps up to eight records of (server address/port, observed sockaddr). A changed
observation from the same server clears tracking. Equal observations from different servers set a
"same mapping" flag. Reception from an unexpected endpoint (`1009`, `8005`) sets an "other
endpoint" flag. READ. The NAT code is:

| Code | Condition (READ) |
|---:|---|
| 1 | Other-endpoint flag set |
| 0 | Fewer than two records |
| 2 | Same mapping across servers |
| 3 | Different mappings |

Codes 2 and 3 correspond operationally to endpoint-independent and endpoint-dependent mapping;
code 1 to successful alternate-source reception. INFERRED. These MUST NOT be mapped to RFC NAT
names without observation. INFERRED. Extra environment state may adjust the local value. READ.

R5. Server port probing: a P2P request goes to the selected server and, when options allow and the
local NAT code is not 3, also to an extended port: base = another listed server port + 1 (default
10002), plus `((time_ms % 60) * 5 + counter % 5) % 300` (time term 75 if time is unavailable);
the counter increments. This probes server ports, not peer endpoints. READ.

## UDP establishment

R6. Initiation: the connect routine allocates a SID and a new RID, request nonces, master AES
material and an EC key pair, then starts LAN search and master query. Reply-driven state for UDP
(READ):

| Step | Transition |
|---|---|
| Master query sent, reply received | 1 → 2 |
| Hello sent, reply received | 3 → 4 |
| Precheck sent, reply received | 5 → 6 |

UDP and TCP state variables are separate. READ.

R7. Parallel mode, after precheck state 6: start P2P probing (unless the peer NAT code is 10) and
relay work together. P2P success (state 3) gives selection result 4; relay success (state 5) gives
5; failure of both gives public error -42. P2P success is checked before relay success. READ.
Which success "wins" when both arrive close together depends on task scheduling. INFERRED.

R8. Sequential mode, after precheck: if local NAT + peer NAT < 5, try P2P for 6000 ms, else skip to
relay; on P2P failure or expiry start relay. NAT sum 6 gets a special 400 ms attempt. Disabled
LAN/P2P options, P2P timeout 0 and older peer protocol are handled by the task creator. READ.

R9. UDP relay information (app library, READ):

1. A relay result 0 from a server in request state 1 or 2 moves that server to accepted (3).
2. If the session relay state is 1 or 2 and no server is yet chosen, this server is marked
   chosen, its endpoint stored, session relay state set to 4, and `0241` is sent at once, then
   every 500 ms for up to 60000 ms.
3. `0241` goes to each accepted server with protocol > 9 or the chosen mark. The **chosen server
   gets flag 1** (LE32 at H+44); other accepted modern servers may get flag 0.
4. The task stops on relay state 5, LAN state 6 or P2P state 3, and sets relay state -1 on expiry.
5. Repeated ready results in state 4 do not restart the task. Pending relay does not cancel
   parallel direct probing.

R10. On a modern relay result for a session already connected (status 2), the app sends `0241`
with flag 0 to the responding server (except in sequential mode 2). This is not a periodic
initiator. READ. The server's meaning of flag 0 versus 1 is unresolved (server-side).

R11. The original relay-request task is not deleted on ready; it ignores state 4 and still sets
relay state -1 on its own expiry. The `0241` task's 60000 ms lifetime therefore does not promise
60 more seconds after ready. READ.

R12. LAN establishment: a new-form `0602` response must carry a cookie and UID matching a
connecting session. Result 1 or 7 lets the client send `0601` with connect flag 2 to the
responder, install direct path 0 and set LAN state 6. Results: 3 refusal, 4 port rejected, 5 wrong
auth key, 6 no key auth. Route flag `0200` also means refusal. Old 36/168-byte responses trigger
punch-to plus knock and short-RID compatibility. READ.

## UDP/TCP race

R13. The connect loop polls every 10 ms, checks cancellation and errors each pass, and starts
LAN/UDP work plus a TCP task (20 ms interval) unless TCP is disabled. A usable UDP precheck
selects UDP and cancels the TCP work; selecting TCP starts the relay worker (20 ms), sets TCP
state 14 and cancels UDP work. READ.

R14. TCP gate: when not refused and TCP state is 12, a selection counter is tested **before** 10 is
added to it. The gate opens when the counter is > 1499 (no UDP master/precheck response flag) or
> 4999 (flag set). Once open,
TCP is chosen only if the connection mode is TCP-only or the general state is -1 or 2. Some
UDP-negative/TCP-terminal combinations skip the wait. READ. These are accumulated poll counts,
not exact delays. INFERRED.

R15. TCP worker states, app library (device library counterpart in brackets). READ.

| State | Action / exit |
|---|---|
| 1 → 2 | Open TCP sockets to listed masters [same] |
| 2 | Connected socket: reset stage counter, go to 4; >59999 ms accumulated or no socket left → 3 [same] |
| 4 | Query master on connected sockets; >59999 → 6; valid master reply → 5 [legacy query] |
| 5 → 7 | Open P2P-server TCP sockets (cached list may start at 5) [same] |
| 7 | Connected: reset counter, → 11 [→ 10]; no sockets or >59999 → 9 |
| 11 | Send precheck (record type 2, `0217`) initially and every ≥1000 ms; >59999 → 13; valid reply → 12 [10; timeout → 12; success → 11] |
| 12 | Precheck done; TCP connect task removed; selector arbitrates with UDP [11] |
| 14 | Relay request `020c` (timeout value 60, option 5) to servers in state 11/14; resend ≥2000 ms; >59999 → 16 [13; timeout → 15] |
| 17 → 18 | Relay accepted: select a server, send `0241` flag 1, retry to it every ≥2000 ms (R16) [16/17; legacy `0209`] |
| 18 → 20 | `030e` received: install path 3, ACK `030f`, worker removed [17 → 19, ACK `030c`] |
| 16, 19 | Terminal failure: worker removed, selector fails [15, 18] |

R16. TCP relay-info retry: each call first tests the **previous** accumulated stage counter `T`;
if `T ≥ 60000` it sets state 19; then it adds the elapsed delta to `T`. It scans 32 server slots in
order, needing per-server state 17. A slot is eligible if never sent or `T - last_send ≥ 2000`.
In state 18 only the selected slot is used; otherwise the first eligible slot becomes selected and
the session enters 18. It records `last_send = T` and sends `0241` with flag 1. The scan continues
after setting 19 and can set 18 again in the same call; 19 is terminal only if it survives. READ.

R17. Early exits (READ):

| Condition | Result |
|---|---|
| General state -1 with resolver failure (state 3) | -2 |
| UDP preconnect -1 and TCP 3/6 | -60 |
| UDP preconnect -1 and TCP 9 | -33 |
| UDP preconnect -2 and TCP 3/6/9 | -1 |
| UDP -1, -2 or -3 with TCP 12 | Select TCP |
| TCP 13 | Unavailable/asleep via status helper |
| All populated server entries report "not logged in" (UDP 5 or TCP 11) | -90 |
| TCP relay state 20 | Selection 6 |
| TCP relay state 16/19 | -42 |
| Refusal flag while pending | -40 |

TCP-only mode applies its own failure mapping, not this table. READ.

R18. A client MUST NOT treat one server's negative reply as failure of all competing paths.
INFERRED (consistent with R17 "all populated" rule, READ).

R19. On success the app reports success, removes attempt task types 1 (UDP) and 4 (TCP), closes
unused master sockets and releases unused P2P TCP sockets; the relay connection in use stays
referenced. Most failures clean all tasks, release resources and the session; the uninitialized
(-12) exit path is an exception. READ. A late
callback MUST NOT revive a finished attempt; implementations SHOULD guard callbacks with an
attempt generation token. INFERRED.

R20. Modern records over TCP: no extra length prefix. The app requests missing bytes for a short
record and otherwise requires `received == 12 + body_length` (max 1416); it does not split
coalesced modern records as the legacy path does. READ. New implementations SHOULD delimit
records by the 12-byte envelope and its LE16 length, independent of read boundaries. INFERRED.

R21. Device shared TCP relay failure: the device invalidates sessions on path 3, clears relay
endpoint and state, releases the connection, and reconnects if TCP fallback is enabled. When all
server connections fail and reconnect-on-all-failed is set, it schedules a reconnect task with
interval `300000 ± (rand() % 120000)` ms and lifetime 300000 ms. The task's callback first sets
its execution flag, connects on a later invocation if TCP is still enabled, then deletes itself.
The app library keeps the same interval expression. READ. This does not prove an exact
delay or an infinite retry policy. INFERRED.

## Try-port traversal

R22. Trigger: a valid punch instruction with local NAT + peer NAT = **5** adds a try-port node typed
by the **local** NAT code. Type 2 varies target ports; type 3 varies local source sockets. READ.

R23. The try-port task runs every **5 ms** for up to **60000 ms**, started once. Each entry sends
`0401` (device role) or `0403` (client role) with UID/RID, requested port and SDK version, on the
traversal socket or the normal P2P socket. A send is skipped unless the target IPv4 differs from
the saved local observed IPv4 **and** the port differs from the saved local port. READ. This is
separate from the ordinary 50/200 ms knocks.

R24. Type 2 generator (READ): up to eight candidate addresses with host-order base ports. For step
`i = 0..1023`, clamp base to 1366..65193, then:

- `i % 3 == 0`: try `(base + floor(i/3) + 1) mod 65536`;
- `i % 3 == 1`: try `base - (floor(i/3) + 1)`;
- `i % 3 == 2`: draw `floor(rand() * 65535 / 2147483647)` until ≥ 1025.

One list holds a candidate per populated address, up to the zero-address sentinel. After 1024
steps reset `i`; with the **pre-increment** pass count `c`, if `c ≥ 2` and even choose one random
base ≥ 1025 for all slots, else restore the advertised bases; then `c = c + 1`. New type-2 node
pass limit `L = 3`.

R25. Type 3 generator (READ): open a pool of **230** UDP sockets and send from each socket index
0..229 to each populated advertised endpoint. New node `L = 1`. Another pass is eligible only when
the seconds difference exceeds 4.

R26. Nodes run round-robin; a node is removed when `c` reaches `L`. When no work remains, a helper
fails, or the lifetime expires, cleanup removes nodes, releases **unused** traversal sockets and
clears the started flag. A successful association keeps a reference to its socket; teardown
releases it. A retained traversal socket MUST NOT be closed just because the generator stopped.
READ / INFERRED.

R27. Updates to an existing node keep `c` and `i`. Endpoint equality is IPv4 + port. READ.

| Case | Local type 2 | Local type 3 | Endpoints |
|---|---|---|---|
| Same UID/RID, all endpoints duplicate | `L` unchanged | `L = L + 1` once | Unchanged |
| Same UID/RID, new endpoints | Per insertion `L = c + 3` | Per insertion `L = c + 1`; then once `L = L + 1` | Prepend each new endpoint and base; shift others; drop the eighth when full |
| Different UID/RID sharing an endpoint | `L` unchanged; no new node | `L = L + 1`; no new node | Keep existing identity and slots |

These are assignments, not maxima. Type 3's final increment also applies with no supplied
endpoints. READ.

R28. Implementations SHOULD use checked eight-entry arrays and explicit unsigned port arithmetic.
The algorithm alone does not predict packet counts. INFERRED.

## Attempt and cache lifetimes

| Object | Rule |
|---|---|
| Recent client RID list | Entries removed on lookup when ≥ 20000 ms old; while kept, an entry with the same format and value **and marker 1** is rejected. READ. Not a general packet TTL. INFERRED. |
| Creating session / pre-session | Recycler every 10000 ms, lifetime 60000 ms; reaching connected (status 2) removes it; on expiry only still-creating device-owned state is reclaimed. Connected sessions do not expire at 60 s. READ. |
| NAT observations | At ≥ 25000 ms, update the last-connect time, then clear NAT records only if exactly one session is connecting. READ. |
| New client attempt | New RID ([session: Identity](session.md#identity)), nonces, master AES material and EC key; never reuse a cancelled attempt's callbacks or allocation. READ (initialization) / INFERRED (guard). |

Recent-RID markers. Both libraries keep one recent-RID list, holding the RID words, the format,
the time added and a marker. READ (device firmware 64- and 32-bit builds; app library). The lookup
rejects only entries with marker 1:

| Added by | Marker | Effect while kept |
|---|---|---|
| LAN-search connect precheck refused because the requested IOTC port is not accepted (reply code 4) | 1 | Packets with that RID are rejected by the handlers listed below; what each handler sends back was not compared |
| Local session close (device and app) | 0 | None: no lookup tests marker 0 |

All rows READ. The device runs the lookup on LAN search, `KNOCK2`, `KNOCK_R1`, `PUNCH_TO2`,
`ALIVE_D2C` and `RLY_REQUEST_R2`; the app runs it on `0428` and `030d`. READ. A just-closed RID
is therefore not refused by this list. After a close the session is released, so a knock that
reuses that RID finds no session and is handled as a new one. INFERRED. The inspected close and
alive paths keep no other state that would catch such a reuse. READ (for those paths). Every SDK
cache was not enumerated, so other such state is not ruled out. unresolved. A client SHOULD NOT reuse
an RID from a closed or refused attempt. On a refusal (code 4) it SHOULD use a new RID, or wait at
least 20000 ms. INFERRED (policy).
