# Events: envelope, delivery and ordering

Part of the [events chapter](../events-overview.md). This file covers the event envelope, line
framing, the event channels (ports and processes), who receives each event, peer forwarding and
ordering. Below it sits the TCP stream ([LAN discovery and ports](../../transport/lan-discovery.md),
[session handshake](../session-handshake.md)); above it sit the helper families
([families.md](families.md)) and the per-event cards (`docs/<service>/events/`).

Basis: static analysis of firmware 9.31 (64-bit "D64" and 32-bit "D32" imager, guider and
updater) and app 3.3.2, plus sanitized wire captures from 2026-10-12. Labels follow
[CONVENTIONS.md](../../../CONVENTIONS.md). READ claims are D64 unless stated; D32 has equivalent
envelope helpers (READ).

## Envelope

An event is an unsolicited JSON object sent by the device. It is not a reply to a request.

R3. Every event object has two string members, `Event` and `Timestamp`, followed by
event-specific members at the top level. READ. Nested objects occur only where an event card
names them.

R4. An event has no `jsonrpc`, `id`, `method` or `result` member, and no unconditional `code`.
READ. A receiver MUST classify a line as an event by the presence of a top-level `Event` string,
and MUST NOT require any of those reply members on it.

R5. `Timestamp` is a JSON **string** holding monotonic seconds with exactly nine fractional
digits (nanoseconds), formatted as `%ld.%09ld` from clock id 1. READ. Clock id 1 is `CLOCK_MONOTONIC` on Linux, so it is
not UTC and not Unix time (INFERRED); its origin is unspecified (typically boot). A client MUST NOT convert it to a
calendar date. A client MAY use it to order or difference events from the same device process.
OBSERVED (2026-10-12): `Timestamp` arrived as a string with nine fractional digits.

R6. One ordinary broadcast creates its timestamp once, so all recipients of that broadcast see
the same `Timestamp`. READ.

R7. The device writes `Event` first and `Timestamp` second (READ, envelope constructor). A
client MUST NOT depend on member order. A stand-in device SHOULD keep this order.

Typed sketch (placeholders, not values):

```text
{"Event":<name string>,"Timestamp":<monotonic string>, <event-specific members>...}
```

## Framing

Events share the JSON-over-TCP stream with RPC replies on the same socket.

```abnf
event-line   = event-object CRLF
event-object = "{" event-member "," ts-member *( "," member ) "}"   ; JSON object (RFC 8259)
event-member = %s"\"Event\":" DQUOTE 1*name-char DQUOTE
ts-member    = %s"\"Timestamp\":" DQUOTE 1*DIGIT "." 9DIGIT DQUOTE
name-char    = ALPHA / DIGIT / "_"
member       = <any JSON object member>
```

The grammar is descriptive of what the device sends; JSON whitespace is absent in device output
(READ for the imager serializer) but a client MUST accept it.

R8. The imager sender removes every LF byte from the serialized text, keeps CR bytes, appends a
literal CRLF and writes the line under a per-socket write mutex. READ. There is no length prefix,
subscription id, acknowledgement, replay cursor or global sequence number. READ.

R9. A client MUST split the stream on line ends. The device's own input reader treats CR and LF
each as a delimiter (READ); a client SHOULD do the same and ignore empty lines. An escaped `\n`
inside a JSON string is not a delimiter.

R10. Event lines and reply lines are interleaved on one socket. A client MUST dispatch each line
by content: a top-level `Event` member means event; a `jsonrpc`/`id` member means reply.
INFERRED from R4.

## Channels

The device runs several JSON servers. "Channel" labels are used in the event index.

| Label | Endpoint | Process | Role for events |
|---|---|---|---|
| I | TCP 4700 | main imager | Default event channel, also RPC. READ. |
| I2 | TCP 4701 | main imager, second server | Separate RPC server with its own connection map. Not shown to receive the 4700 broadcasts. READ. |
| W | TCP 4702 | auxiliary (wide-camera) imager | Its own events; the main imager forwards them to I ([Peer forwarding](#peer-forwarding)). READ. |
| G | TCP 4400 | guider (mount, guide camera) | Its own events; the main imager forwards them to I ([Peer forwarding](#peer-forwarding)). READ. |
| U | TCP 4350 | updater | [`Version`](../../../docs/control/events/Version.md), [`Receive`](../../../docs/updater/events/Receive.md), [`Update`](../../../docs/updater/events/Update.md) only. READ. |

R11. Binary and media endpoints (TCP 4800, 4801, 4804, 4720, 4361, RTSP 4554/4555, UDP
discovery) are not event streams. A numeric `port` member inside an event names a server; it
does not make that server an event channel. READ. TCP 4361 (binary upload) causes `Receive`
events on 4350 but carries no JSON events itself. READ.

R12. A client that wants all imager, mount and guider events SHOULD connect to TCP 4700 only.
Connecting to 4400 or 4702 as well yields duplicates of forwarded events. INFERRED.

## Recipients

R13. Ordinary broadcast: the sender writes to every connection in that server's connection map,
with no check of verified, master/guest or internal/external status. READ. A connection that is
admitted but never verified therefore still receives broadcasts, even though its ordinary
requests may be silently consumed. READ. Being a recipient does not guarantee cadence, delivery,
or that the connection is kept open (see R18).

R14. Special recipient rules, READ:

| Event | Recipients |
|---|---|
| `Version` | Only the socket that just connected (connection greeting), on 4700, 4400 and 4350. |
| [`Alert`](../../../docs/control/events/Alert.md) (connection-limit form) | Only the rejected socket, just before it is closed. |
| [`Client`](../../../docs/control/events/Client.md) | Only eligible clients when guest mode is on; `is_master` is personalized per recipient. A per-connection client-info flag can exclude a connection. |
| `Receive`, `Update` | Every 4350 connection whose peer IP string equals the target IP; several sockets from one IP all match. |

R15. Event delivery rules are separate from authentication, admission and command permission
(see [session handshake](../session-handshake.md)). READ.

OBSERVED (2026-10-12): a passive connection to TCP 4350 received a `Version` greeting with
exactly `Event`, `Timestamp` and `name`, without sending any request. Two receive-only 4700
connections over the same 300 s window received the same 57 events; none arrived on only one.

## Peer forwarding

The main imager connects to the guider (4400) and, on dual-camera models, reads the auxiliary
imager (4702) as a client.

```text
 guider (4400)        aux imager (4702)       main imager               client (4700)
      |  event line         |                      |                          |
      |--------------------------------------------> contains "Event":" ?     |
      |                     |                      |--- same line, unchanged -->|
      |                     |  event line          |                          |
      |                     |--------------------->|--- same line, unchanged -->|
```

R16. The main imager forwards a peer line to all I connections unchanged when the line contains
the exact substring `"Event":"`. READ. The test is lexical: whitespace around the colon defeats
it. A stand-in guider or auxiliary imager MUST serialize `"Event":"` with no whitespace.
INFERRED consequence.

R17. The auxiliary imager process does not forward events it reads from 4400, so guider events
reach 4700 once, through the main process only. READ. The main imager also handles some guider
events locally ([`MoveByAngle`](../../../docs/guider/events/MoveByAngle.md), [`GuideStarLostTooMuch`](../../../docs/guider/events/GuideStarLostTooMuch.md), [`MountConnection`](../../../docs/guider/events/MountConnection.md), [`AutoOpenCamera`](../../../docs/guider/events/AutoOpenCamera.md),
[`AppStateChange`](../../../docs/control/events/AppStateChange.md), [`MountMode`](../../../docs/guider/events/MountMode.md)); local handling does not change the forwarded line. READ.

## Observer lifetime

R18. Outgoing events do not renew a connection's receive-idle clock. An accepted external
connection becomes eligible for closure after more than 15000 ms with no received bytes, even
while events flow to it. Any received fragment renews the clock; a complete request is not
needed, and a successful asynchronous input completion also renews it. READ. Actual closure can lag because the check is periodic. READ. Exceptions exist for
internal clients and connections with an active input handler (READ, path-specific).

R19. A listen-only client SHOULD send a harmless request (for example a pure getter) at an
interval well below 15 s to stay connected. INFERRED from R18.

R20. Closing a 4700 or 4702 socket stops a polar-alignment run only when that socket owns it. No
other operation is stopped by a close: no exposure, stack, goto, plan or view. READ. On close the
device also updates its "client connected" indicator, and, with guest mode on, drops the
socket's master status (clearing the master when none remain) and sends a `Client` event to the
remaining clients. READ. Closing a 4701 connection has no side effects beyond dropping the
connection. READ.

## Ordering

R21. Writes to one socket are serialized (no interleaving inside a line). READ. Beyond that,
events come from many worker threads and race with each other and with RPC replies. READ.

R22. There is no guaranteed "reply before start event" or "reply before completion event", no
global FIFO across threads, no replay after reconnect, no delivery guarantee after a disconnect,
and no fixed event frequency. READ / INFERRED (no such mechanism exists in the inspected code).

R23. Function events update the device's cached function tree before sending, and an end event
can be suppressed while the cache still changes ([families.md: F suppression and lifecycle flags](families.md#f-suppression-and-lifecycle-flags)). READ. In
9.31 only a few internal helper workers use suppression (families.md R42a). READ.
A client that needs the current state SHOULD read it with a getter (for example the view-state
getter) after connecting, rather than wait for events.

OBSERVED (2026-10-12): a [`Setting`](../../../docs/control/events/Setting.md) event arrived about 63 ms before a [`ViewPlan`](../../../docs/control/events/ViewPlan.md) working event
after an accepted `set_view_plan`; reply-versus-event order was not captured. Two [`Stack`](../../../docs/control/events/Stack.md)
events about 0.1 ms apart carried different payload variants of the same name.

OBSERVED (2026-10-12, firmware not matched to 9.31, device imaging a stored plan, two
receive-only 4700 connections for 300 s): 29 [`PiStatus`](../../../docs/control/events/PiStatus.md) (temperature only), 20 `Exposure`, 8 `Stack`
and 1 [`DiskSpace`](../../../docs/control/events/DiskSpace.md). One exposure cycle took about 63 s: a legacy `Exposure` start
(`exp_us`, `gain`), a `Stack` pair about 9.4 s later (one of each producer shape), and at about
62 to 63 s a burst of four `Exposure` events (two legacy `page`/`state`, two function-style with
`exp_ms`, `port`, `lapse_ms`, `route`) followed by the next start. No `ViewPlan` or [`Client`](../../../docs/control/events/Client.md)
event and no name outside the [event index](../events-overview.md#event-index) appeared. These
counts describe one session, not a rate contract.

## Client rules

These rules collect the client obligations of this chapter.

R24. **Merge deltas.** Many events carry only the members that changed ([`PiStatus`](../../../docs/control/events/PiStatus.md), `Setting`,
and function events whose formatter omits empty fields). A client MUST merge each event's
members into retained per-device state and MUST NOT treat a missing member as false, zero or
removed. INFERRED from the delta producers ([families.md: Worked example: PiStatus deltas](families.md#worked-example-pistatus-deltas)).

R25. **Tolerant parsing.** A client MUST ignore unknown `Event` names and unknown members, MUST
accept any member subset, and MUST NOT reject an event because a member it expects is missing.
A client MUST accept both integer and real JSON numbers where a number is expected, and SHOULD
treat unknown `state` strings as "other" rather than failing. INFERRED (event payloads are open
and vary by producer, build and model).

R26. **Select by producer.** One `Event` name can have several payload variants (for example
[`Exposure`](../../../docs/control/events/Exposure.md), `Stack`, [`Target`](../../../docs/control/events/Target.md)). A client SHOULD choose the interpretation from the members
present (for example `lapse_ms` and `route` indicate the function-event variant), not from the
name alone. INFERRED.

R27. **No reply/event ordering.** A client MUST NOT assume an event arrives after, or before,
the reply to the request that caused it, and MUST correlate events to operations by `Event`,
`state` and `route`, not by arrival position relative to replies. READ / INFERRED (R22).

R28. **Not every transition is sent.** A client MUST NOT require a `working` event before an end
state, nor exactly one end state per operation. A late joiner sees no earlier transitions.
READ (no previous-state comparison or deduplication in the sender).

R29. **Route is optional.** `route` is function ancestry, not an address, and can be absent on
legitimate events. A client MUST NOT require it. READ.
