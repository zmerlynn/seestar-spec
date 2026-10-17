# Control session: heartbeats, initialization, ordering and secondary servers

Part of the [session handshake](../session-handshake.md) chapter. It specifies the idle clock
and heartbeats, the app's initialization writes, ordering between replies and events, a full
message flow, and the secondary servers 4701 and 4702. Below it are the connection, framing and
envelope rules of the [main chapter](../session-handshake.md) and
[verification and roles](verification-and-roles.md); events themselves are in the
[events overview](../events-overview.md). Labels and RFC 2119 usage follow
[Conventions](../session-handshake.md#conventions) of the main chapter.

## Heartbeats and the idle clock

R40. The device keeps a per-socket activity time. It is set on accept and renewed whenever bytes
are received, whether or not they form a complete, valid or authorised request, and when an
asynchronous handler completes. Sending replies or events does not renew it. READ.

R41. An external connection with no received bytes for more than 15 000 ms (the first
eligible whole-millisecond duration is 15 001 ms) becomes eligible for closing. Checks run
periodically and with a 5 s select timeout, so the actual close can come later. Internal
connections are exempt, and the socket whose input is being handled asynchronously is exempt
while that handler runs. READ. The same clock applies to the image/file sockets; the guider has
an equivalent check, and the updater uses a separate clock. READ. `test_connection` has no
special effect beyond being received bytes. READ.

R41a. The HTTP file server keeps connections alive and announces a keep-alive timeout and a
maximum request count in a `Keep-Alive` header; a client SHOULD honour those values rather than
assume any. READ. The values announced are the library defaults (at most 5 requests, 5 s), see
[files-and-album.md R19](../../media/files-and-album.md#http-80). INFERRED. The RTSP server sets TCP keep-alive on its
sockets and drops a connection only when the peer closes it, a receive fails, or its session is
torn down; no idle timeout was found. INFERRED.

R42. A client MUST send something at least every 15 s on an external connection. It SHOULD send
`test_connection` (no params) as the heartbeat; the app sends it when more than 2000 ms have
passed since the last heartbeat. READ (app). The reply is `result: "server connected!"`, code 0.
READ. OBSERVED (2026-10-12): about 159 ms to the reply while imaging. See
[test_connection](../../../docs/control/methods/test_connection.md).

R43. OBSERVED (2026-10-12): through the tunnel (an internal connection), a receive-only 4700
stream was not closed at 15, 60, 120, 180 or 300 s. OBSERVED (2026-10-16): through the tunnel, one
4700 connection that sent no bytes for 600 s, while it received 22 `PiStatus` events and nothing
else, stayed open, and five reads on it afterwards returned code 0 in 127 to 193 ms. Tunnel-level
heartbeats were not measured. Both agree with the internal exemption; LAN-direct connections fall
under R41.

R44. Closing a socket cleans up its connection state. Closing the 4700 or 4702 socket that owns
a running polar alignment also stops it. No other operation is stopped by a close. READ. The
device also updates its "client connected" indicator and, with guest mode on, drops the socket's
master status and sends a `Client` event to the remaining clients
([events/envelope.md](../events/envelope.md) R20). READ. A 4701 close has no side effects beyond
dropping the connection. READ.

OBSERVED (2026-10-15): with four sockets open on one tunnel session, one closed with
a read outstanding. The other two each completed ten further replies over about 22 s, neither
was disconnected, and no `Client` event or visible role change followed.

## Initialization after verification

Non-normative. The app (READ) and the iOS app (OBSERVED 2026-10-12) send writes during
initialization, so connecting is not a passive probe.

OBSERVED iOS order on each connect: `get_verify_str`, `verify_client`, `get_device_state`
(empty-object params), `set_setting` (`lang`), `pi_set_time`,
[`set_user_location`](../../../docs/guider/methods/set_user_location.md),
`iscope_get_app_state`, `set_setting` (`cli_uuid`, `cli_name`), `pi_get_ap_channel`. The
order repeats on reconnect; later connects sometimes added `get_image_save_path`, and once
`remove_file`. Whether the iOS order also holds in remote mode is unresolved.

OBSERVED (2026-10-17), firmware 9.75, app 3.4.0, one LAN session captured end to end (app plaintext
on the control leg): the verification pair (`get_verify_str`, `verify_client`) was followed by
`get_device_state` (keyless), then by one batch sent before any of its replies — `set_setting`
(`lang`); `pi_set_time` and `set_user_location`; `iscope_get_app_state`; `set_setting` (`cli_uuid`,
`cli_name`); `pi_get_ap_channel` — all code 0, same order as the general case above.
`test_connection` with `id` 101 followed, repeated every 5 s with the same id each time rather than
an incrementing one. A `remove_file` (a fixed temp-upload text file name, not image data; reply an
integer 0) closed the sequence; it did not repeat on reconnect. The iOS app can have more than one
request outstanding at once on 4700 (it does not match the Android app's one-at-a-time rule of R44a,
which is specific to that app).

OBSERVED (2026-10-17), firmware 9.75, same session, reconnect: 30 s before the owner force-closed
the app, it sent an unprompted `set_user_location` (`force`, `lat`, `lon`), code 0, consistent
with "when the user selects a location" above. The connection then closed normally after 201 s.
8 s later a new connection opened and repeated the identical verification-plus-batch sequence
byte-for-byte in method order, all code 0, except that `remove_file` did not recur.
`get_verify_str`'s reply took 3.37 s on the first connection and 0.76 s on the reconnect; both
are well within the 15 s idle budget (R41).

The Android app 3.3.2 uses a different order (READ). On every control socket it opens, in every
connection mode (nearby, LAN and remote over the tunnel's loopback port), it first sends
`get_verify_str` and then `verify_client` (skipped when `get_verify_str` answers 103), and then
queues one initialization sequence: `pi_set_time`, `set_setting` (`lang`), `set_setting`
(`cli_name`, `cli_uuid`), `get_device_state` (`keys` `client`, `camera`, `second_camera`),
`get_setting`, `iscope_get_app_state`, `get_device_state` (`keys` `device`), then
`get_device_state` without params, whose device serial feeds the serial check below. The
sequence is the same on reconnect, since it runs for each new socket, and only the serial check
depends on the mode. It does not contain `set_user_location` or `pi_get_ap_channel`. READ (app
3.3.2). The iOS and Android orders differ, so neither is a protocol requirement beyond verifying an external connection first
([verification-and-roles.md R30](verification-and-roles.md#enforcement)). INFERRED.

R44a. In Android app 3.3.2, other requests cannot interleave with the initialization sequence. One
socket thread runs a priority queue and a normal queue. It takes one queued action at a time, from
the priority queue first, and runs it to completion. Within an action it sends one request and reads
lines until that request's reply arrives, handing non-reply lines to the event handler, before it
sends the next request. The app therefore never has more than one request outstanding on the control
socket. Requests made before the socket is marked connected fail at once, and actions left from an
earlier session fail when a new socket opens. The socket is marked connected after verification and
before the initialization sequence is queued on the normal queue, so a priority action, or a normal
action queued in that short window, can run before the whole sequence. Nothing runs in the middle of
it. READ (app 3.3.2).

The app's initialization (READ) sends time, language and client-name settings and fetches the
client, settings, app and device state. On a LAN connection it requires a nonblank device serial
number and adopts the serial the device reports in place of its saved one, rather than rejecting a
mismatch.

R45. A client that only wants to observe SHOULD skip these writes. A client that sets the clock
(`pi_set_time`) or location changes device state seen by every other client. READ.

## Ordering

R46. Writes to one socket are serialized, so lines never interleave. READ.

R47. There is **no ordering guarantee between a reply and the events its request causes**. Worker
threads broadcast events while the dispatcher writes the reply; a start event can arrive before
the reply, and a completion event can too. READ. Traced end to end for `scope_goto` ([goto-and-manual-motion R15](../mount-and-motion/goto-and-manual-motion.md#raw-slew-scope_goto)). OBSERVED once (2026-10-12): after
`set_view_plan`, a [`Setting`](../../../docs/control/events/Setting.md) event came about 63 ms before the [`ViewPlan`](../../../docs/control/events/ViewPlan.md) working event;
reply-versus-event order was not recorded.

R48. Replies to requests on one connection are written in processing order for synchronous
handlers (INFERRED); relayed and asynchronous handlers can finish later. A client MUST match by
`id` and MUST NOT assume FIFO replies. INFERRED.

OBSERVED (2026-10-15): two sockets of one tunnel session sent requests carrying the same `id`
within 0.3–0.7 ms, five times. Each reply reached only the socket that sent its request, and no
reply was duplicated or crossed over (30 of 30 per socket). Reply routing is per connection, so a
client does not need ids that are unique across its connections. INFERRED from this sample.

OBSERVED (2026-10-15): across 160 serial request/reply pairs of read-only methods, no event
arrived between a request and its reply; the only events seen (`PiStatus`) arrived between
replies. Requests were mostly one at a time per socket, so this does not show whether a reply can
be held behind queued events, and it does not weaken R47.

OBSERVED (2026-10-17), firmware 9.75: on one TCP 4700 connection, a request whose root object repeats `method` is dispatched as the last `method` given, in either order (`test_connection` then `get_view_state`, and the reverse), and the reply echoes that last `method`. Within 4700, duplicate members inside `params` probably follow the same last-wins rule, since the same parser likely reads them. INFERRED, not tested. Other services (4400, 4350, 4701, 4702, discovery) were not tested. This does not change [device-state-and-settings.md R9](../device-state-and-settings.md#reading-get_setting), which covers duplicate members in replies.

OBSERVED (2026-10-15): with 3–5 read-only requests pipelined per socket on two sockets (520
batches, 2,079 replies, all code 0), no reply came back out of send order. A `PiStatus` event
arrived between two replies of the same batch once, and before every reply of its batch twice
(the first reply followed 100–156 ms later). Events therefore interleave with pipelined replies;
a client MUST NOT treat the frames between a request and its reply as belonging to that request.
The sample is consistent with R48's FIFO inference for synchronous handlers but does not replace
matching by `id`. Frame boundaries were seen on the client side of a tunnel only.

R49. There is no global event sequence number, acknowledgement or replay. Events broadcast
while a client is disconnected are lost. READ. A client SHOULD re-read state after reconnecting.
INFERRED.

R50. Events go to every retained connection of the server, including unverified and guest
connections. READ. Details: [events overview](../events-overview.md).

OBSERVED (2026-10-15): on three concurrent sockets of one tunnel session, each `PiStatus` arrived
once per socket with byte-identical frames (2/2/2), and still matched on the two remaining
sockets after one closed (3/3). No other event type occurred in that window.

## Message flow

```text
Client                                         Device (imager, TCP 4700)
  |------------------- TCP connect ----------------->|
  |                                                  | count distinct external IPs
  |<-- {"Event":"Alert","code":429,...} + FIN -------|  (only if over the limit)
  |<-- {"Event":"Version",...}\r\n ------------------|  greeting, this socket only
  |-- {"id":1,"method":"get_verify_str"}\r\n ------->|
  |<-- {...,"result":{"str":"<32 chars>"},"code":0,"id":1}\r\n
  |   [sign challenge, base64]                       |
  |-- {"id":2,"method":"verify_client",              |
  |    "params":{"sign":"..","data":"<32 chars>"}}\r\n>|
  |<-- {...,"result":0,"code":0,"id":2}\r\n ---------|  socket now verified
  |-- {"id":3,"method":"start_x",...}\r\n ---------->|
  |<-- {"Event":"X","state":"working",...}\r\n ------|  may come before the reply
  |<-- {...,"method":"start_x","result":0,"code":0,"id":3}\r\n
  |<-- {"Event":"PiStatus",...}\r\n -----------------|  broadcasts at any time
  |-- {"id":4,"method":"test_connection"}\r\n ------>|  at least every 15 s
  |<-- {...,"result":"server connected!","code":0,"id":4}\r\n
  |-- {"id":5,"method":"scope_get_ra_dec"}\r\n ----->|  not in imager table
  |                                                  |---- original text ---> guider 4400
  |                                                  |<--- guider reply ------  (<= 10 s)
  |<-- {...,"id":5}\r\n -----------------------------|
```

`start_x` and `X` are placeholders.

## Secondary servers 4701 and 4702

R51. TCP 4701 is a separate request/reply server in the main imager with its own connection map.
It serves the same method set as 4700, dispatched directly without the guest/master restriction,
without the connect greeting and without close side effects. It still requires verification.
READ. The guider relay is not used on 4701. INFERRED. A client MUST NOT expect 4700 broadcasts
on 4701. READ.

R52. TCP 4702 is the auxiliary imager process (wide camera), the same binary in another role.
It uses the same main and guest tables and the same connect and close behaviour as 4700, and has
its own event stream; methods that only work there reply 210 `not supported` on the main process.
READ. The main
process reads 4702 events and re-broadcasts them unchanged on 4700. READ. The app talks to
4700 only (INFERRED); a client SHOULD do the same.

R53. Both ports are in the verification predicate ([R33](verification-and-roles.md#enforcement)). READ.

## Open questions

- Whether plain same-LAN 4700 without verification behaves as READ (silent consumption). OBSERVED
  (2026-10-17), firmware 9.75: it did not for three methods on one device at one time (see
  [verification-and-roles.md R32](verification-and-roles.md#enforcement)); whether that was the
  device's `secure_communication` switch being off or a per-method exemption is still open.
  Factory mode was never observed.
- Order of the [`Version`](../../../docs/control/events/Version.md) greeting relative to early
  requests. OBSERVED (2026-10-17), firmware 9.75: no greeting reached the client before its first
  request on any of four 4700 connections, but whether the device emits none on this path or
  merely doesn't emit it first is still open (see
  [session-handshake.md R5](../session-handshake.md#connection-lifecycle)).
- Relay error codes and envelopes on guider timeout or connect failure.
- End-to-end Unicode handling; duplicate-key handling inside `params` on 4700 (INFERRED last-wins, see [Ordering](#ordering)) and duplicate members on other services.
- HTTP keep-alive default values (R41a).
- Why the keyed `client` section was empty on a tunnel session. OBSERVED (2026-10-17), firmware
  9.75: also empty on a plain LAN connection while the app was connected and verified elsewhere,
  so this is not tunnel-specific; the underlying reason is still open.
- Guest/master identity races, MAC lookup failure, and whether the address-based master restore
  can misattribute master status behind a proxy (R39). With several clients behind one tunnel,
  reply routing and `PiStatus` fan-out were observed ([Ordering](#ordering)); roles and master succession were not,
  because the keyed `client` section stayed empty and no `Client` event arrived. OBSERVED
  (2026-10-17), firmware 9.75, LAN: the same, across a close and reconnect of the official app —
  no `Client` event on either connection and an empty `client` section throughout, so this remains
  unresolved from direct observation on either transport.
- iOS behaviour beyond the observed connect order, including its order in remote mode. Partially
  narrowed (2026-10-17): on firmware 9.75 LAN, the connect order, a reconnect's identical repeat
  (minus `remove_file`), and a mid-session unprompted `set_user_location` are now OBSERVED; remote
  mode is still open.

## Appendix: Validating on a live device (non-normative)

Use the owner's device and the official app, and capture passively first.

1. Capture one normal LAN connect of the official app. Confirm CR LF endings, the verification
   pair, the initialization writes and the heartbeat interval. Keep challenges and signatures
   private.
2. On a verified connection, send `test_connection` and compare the reply envelope and member
   order with [Reply envelope](../session-handshake.md#reply-envelope).
3. Leave a verified LAN connection silent and time the close (R41).
4. Do not test the connection limit, factory paths or malformed input on a device in use.
