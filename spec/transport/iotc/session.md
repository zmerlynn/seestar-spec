# IOTC session identity, liveness and teardown

Part of [Kalay/IOTC session](index.md). This file covers an established IOTC session: identity,
the data path, liveness, path migration, channels, timers, close, and optional device traffic.
Session setup is in [connect.md](connect.md); packet layouts in [framing.md](framing.md). The
[RDT channel](../rdt.md) runs on top, inside DTLS ([dtls.md](dtls.md)). Labels and notation:
[index: Conventions](index.md#conventions).

Basis: static analysis of the app library (app 3.3.2), the device library (firmware 9.31, 64-bit;
32-bit where stated) and the app's Java connection engine.

## Library setup on each side

R1. App: loads the "T" IOTC, RDT, tunnel and global libraries; sets the session alive timeout to
**30**; passes the cloud-supplied licence to the SDK licence setter; initializes the tunnel agent
with arguments (4, 1); connects with the extended tunnel connect call, whose authentication
callback returns the cloud username and password. READ.

R2. Device: sets the licence and alive timeout 30, initializes the tunnel server with (64, 1) and
stores an account and password. Its authentication callback copies the stored password only when
the supplied account equals the stored one. READ. The second initialize argument 1 enables
optional unencrypted LAN-direct forwarding per vendor documentation (DOC); whether a given
connection uses it is unresolved; see Q29 in [00-overview.md: Open-question register](../../00-overview.md#open-question-register).

## Identity

R3. The process-local SID indexes a session object and is not, in general, a wire identifier.
READ.

R4. A session carries RID8 and a format selector. Format 0 keeps both LE32 words; format 1 masks
the first word to 16 bits and clears the second (short RID). RIDs compare equal only with the same
format. The relay allocation ID is a separate LE16 at H+12. READ.

Generation (app library). For a UDP connect the client builds the first word as
`L + H * 0x10000`, where `L` is a per-process counter and `H` a value from the SDK's local network
information. The second word is a value the SDK logs as a partial MAC address. The counter is seeded
on the first connect with `(rand() + time()) mod 0xffff`, with a result whose low 16 bits are zero
replaced by 1. Each later connect uses the previous value + 1. READ. The client does not compare a
new RID with recent or open RIDs, and has no collision retry. READ (no such check in the connect
path). The sources of `H` and of the second word were not traced (unresolved). Uniqueness is
therefore only probable. A counter restarts with every process and depends on the time seed, so a
restarted client can repeat an RID it used shortly before. INFERRED.

## Data path

R5. Data packets carry at most 1388 application bytes, with a per-channel sequence at H+6 and the
datatype at H+15. Layout and opcodes: [framing: Data, alive and close packets](framing.md#data-alive-and-close-packets).
READ.

R6. DTLS records travel inside IOTC data packets with datatype 1; ordinary data uses datatype 0.
The secure-channel reader flags plain data received while expecting secure data. DTLS is never
sent as bare UDP to the peer's IOTC port. READ.

## Session status and liveness

R7. Status (internal, never serialized; READ):

| Status | Meaning |
|---:|---|
| 0 | Unused |
| 1 | Connecting / allocated |
| 2 | Connected |
| 3 | Remote close received |
| 4 | Liveness expired |

Local close recycles the object after task cleanup.

R8. A 1000 ms session-alive task runs per connected session. Each tick: if `counter > timeout`,
set status 4 and call session and channel callbacks with -23; otherwise increment the counter.
While the incremented counter is below 5, alternate sends are suppressed; after that, every tick
sends an alive on the selected route. Matching received data or alive resets the counter. READ.
"30 seconds" is a counter threshold of ticks, not an exact wall-clock deadline. INFERRED.

R9. The connected outbound client sends only selected-route alive packets. Successful connect
removes the negotiation tasks. The inspected client paths contain no periodic modern type-5
keepalive, device registration or initiating re-punch task for an outbound client. READ. Type-5 records are sent only in the device
registration context ([rendezvous-gcm: Record types](rendezvous-gcm.md#record-types)).

R10. Device registration upkeep (app library device code, READ): a 40000 ms task. For the
registration-alive operation it sends a type-5 record when its saved NAT/address is unchanged and
either server registration state is not 1 or fewer than 121 s have passed since the saved marker;
otherwise it sends a type-2 `0127` registration. This is not a client keepalive cadence.

## Path migration

R11. Device, on `0427` (extended body ≥ 8): look up the session by RID, reset its liveness counter,
then update the send address from the packet source without first comparing it to the previous
endpoint. The updater replaces the selected endpoint on direct path 1; on path ≥ 2 it also sets the
path to 1; on path 0 it keeps the endpoint. Both 64-bit and 32-bit builds do this. READ.

R12. Device, on `0407` (body ≥ 12, valid channel < 32): the same RID lookup and the same source
update after dispatch. Invalid channels do not update. READ.

R13. App, on `0428` (body ≥ 8): reject recently refused RIDs ([connect: Attempt and cache lifetimes](connect.md#attempt-and-cache-lifetimes)), find the connected session by RID,
reset liveness, save the WAN endpoint and apply the same updater rules. READ. These updates keep
SID and RID, do not recreate DTLS or RDT, and do not set session status back to connected.

R14. Consequences (INFERRED): a delivered alive or data packet with the existing RID can move a live
direct association to a new client address/port; a direct `0427` can switch a UDP-relayed device
association to direct, followed by the client update on `0428`. No new SID, resume token or
address-update message is needed. This does not prove secure-stream continuity, revival after
timeout, or TCP-relay to UDP migration (the stored connection handle is not replaced). RID and
reversible scrambling are not authentication. Implementations MUST NOT treat RID match as an
authenticated resume credential. INFERRED.

R15. The inspected selected-route alive and registration maintenance contains no periodic
relay-to-direct upgrade initiator. Initial attempt-task cleanup and event-driven server
punch/knock handling are not such a timer. INFERRED.

R15a. Limits of path migration. The protocol as inspected has none of the following (READ for the
absence in inspected code paths; consequences INFERRED):

- an authenticated path probe or challenge. Alive packets carry only the RID, and DTLS AAD
  contains no address, so a route cannot be proven fresh or bound to an endpoint;
- a commit or acknowledgement that both sides now use the new path;
- a rollback to the previous relay path, or a relay-retirement message other than session close
  ([Close](#close));
- a revival of a session whose liveness expired (status 4); R13 updates never restore status 2.

What R11–R13 leave in place is the SID, RID, DTLS state, RDT connection and tunnel channel
table (none is recreated). Whether the relay server keeps the relay path after a switch (and so
whether relay packets still arrive) and its meaning of `0241` flag 0 are unresolved (server-side). An implementation that wants a reliable route
change SHOULD open a new session with a fresh allocation instead.

## Overlapping sessions

R16. The device allows up to 64 sessions (74 pre-sessions); an occupied session is not by itself
a refusal. READ.

R17. The app opens a first tunnel and, if it succeeds and the attempt is not cancelled, immediately
opens a second with the same inputs without closing the first; both must succeed before port
mapping. This is startup provisioning, not a replacement policy. READ.

R18. A fresh second attempt can coexist with a relay subject to capacity, authentication and
backend acceptance; it gets a new RID and secure session rather than resuming. INFERRED. Cloud
control admission is separate ([cloud-auth](../../auth/cloud-auth.md)).

## Channels and the device listener

R19. Enabling a channel (0..31; > 31 returns -26) is local: it sends nothing and creates no remote
listener. A new session enables channel 0 only. Received data is queued only for enabled channels.
The "get free channel" API searches 1..31 and changes local state. READ.

R20. The device's tunnel server accepts a session and creates RDT (secure, with authentication, or
plain) on **channel 0** with a 30000 ms timeout. No direct call to a separate listen, mode setter
or per-channel callback setter was found (indirect callers not excluded). READ.

R21. A client cannot create a second-channel service on the device; only channel 0 is served by
the shipped daemon. INFERRED. The tunnel library has one tunnel record per SID
([p2p-tunnel](../p2p-tunnel.md)).

## Timers

| Operation | Value | Label |
|---|---|---|
| Session-alive task | 1000 ms interval | READ |
| Alive threshold | SDK default 60; Seestar sets **30** on both sides | READ |
| LAN search retry | 100 ms; lifetime from LAN timeout setting | READ |
| LAN precheck response retry | 100 ms, lifetime 30000 ms | READ |
| Master query / hello / precheck | 500 ms, lifetime 60000 ms | READ |
| Relay request / session-info request | 500 ms, lifetime 60000 ms | READ |
| Knock-response recovery | 500 ms, lifetime 5000 ms | READ |
| P2P task | 200 ms (50 ms for port option ≥ 4); lifetime 60000 parallel, 6000 sequential; NAT sum 6: 200/400 ms | READ |
| Device registration | 40000 ms periodic | READ |
| NAT keep (raw keepalive) | 10000 ms periodic | READ |
| DTLS/RDT creation at tunnel level | 30000 ms | READ |
| App port-conflict retry | one retry after 250 ms on -30002 | READ |

## Close

R22. Local close of a connected session sends three direct close packets, or five relay close
packets, back to back. It notifies channel callbacks, cleans tasks, adds the RID to the recent-RID list with marker 0
([connect: Attempt and cache lifetimes](connect.md#attempt-and-cache-lifetimes)) and releases the session. No
close acknowledgement is awaited. READ.

R23. Callback codes: -22 remote close, -23 liveness timeout, -27 local connect stop. READ. DOC
public meanings also include -42 connection timeout, -60 no master response, -90 offline, -2 DNS
failure. These MUST NOT be confused with the signed wire results in
[framing: Receive catalogue](framing.md#receive-catalogue). INFERRED.

## Optional device traffic

R24. Raw NAT keepalive `cc aa ab ab`: [framing: Raw NAT keepalive](framing.md#raw-nat-keepalive). READ.

R25. Legacy telemetry `0804` (528-byte body, 544 total) goes over the selected UDP/TCP connection;
modern `0806` is not a substitute on that path. No server dependency is established. READ.

R26. Sleep registration replaces the login task with a 200 ms task using the caller's lifetime. It
completes once when responses cover the targets or on expiry. Responses are deduplicated by
endpoint; the list refuses additions at 31 entries. Restoring normal login is a separate caller
action. READ.

## Local API bounds (device library)

Local behaviour, not wire fields. READ.

| API | Rule |
|---|---|
| Channel ON | Channels 0..31; > 31 returns -26. RDT's create guard that tolerates 32 does not make channel 32 usable ([RDT session R31](../rdt/session.md#connection-identity)) |
| Login task setup | Master-resolution override: negative restores default; else clamp 60..86400 s; default 86400000 ms |
| Device online check | 100 ms polling with caller timeout |
| Listen, has-data, read, auth-key update | 10 ms poll sleeps |
| LAN search | 50 ms polling; the extended variant uses caller interval × 1000 µs |
| Secure BIO read | 1388-byte buffer, 20 ms read slices, 100 ms retry sleep when disconnected |
| TCP receive buffer setter | Stores the caller value (zero disables the override); applied as `SO_RCVBUF` only when option bit 0 is set and value nonzero. Distinct from tunnel queue thresholds and RDT flow control |
