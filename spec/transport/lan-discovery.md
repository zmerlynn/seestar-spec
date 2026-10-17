# LAN discovery and device selection

This chapter covers how a client finds a Seestar on the local network and chooses the address
it then dials. It sits below the JSON control stream ([session handshake](../control/session-handshake.md))
and beside the remote path ([Kalay/IOTC session](iotc/index.md), [P2P tunnel](p2p-tunnel/index.md)).
It specifies the app-level UDP 4720 scan, the device responder, how the app picks LAN or remote
targets, the separate Kalay LAN search (opcodes 0601 to 0604), and the optional LAN-direct socket
bypass of the tunnel. The full port list is in [ports.md](ports.md). Machine-readable entry:
[`discovery/scan_iscope`](../../docs/discovery/methods/scan_iscope.md).

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients and stand-in devices. Sentences saying what "the device" or "the app" does are
descriptions.

Labels (see `CONVENTIONS.md`):

- **READ**: seen by static analysis of firmware 9.31 (64-bit imager build unless stated, 32-bit
  cross-checked) or of the Android app 3.3.2.
- **OBSERVED**: seen on a real device; date given.
- **INFERRED**: a consequence or interpretation, not seen directly.
- **unresolved**: not established either way.

App behaviour in this chapter is Android 3.3.2. No iOS binary was examined. Device-side rules
(listener, reply schema, framing) probably apply to both phone platforms; app-side retries, UI
gates and target selection do not establish iOS behaviour. INFERRED.

Two different discovery mechanisms exist and MUST NOT be confused:

| Mechanism | Transport | Used by | File |
|---|---|---|---|
| Seestar scan | JSON text over UDP 4720 | App LAN tab; device list | [app-scan.md](lan-discovery/app-scan.md) |
| Kalay LAN search | Binary IOTC frames over UDP 32761 | Kalay SDK during a remote (tunnel) connect | [kalay-search.md](lan-discovery/kalay-search.md) |

## Chapter map

| File | Contents | Rules |
|---|---|---|
| this file | Conventions, chapter map, open questions, validation appendix. | - |
| [lan-discovery/app-scan.md](lan-discovery/app-scan.md) | App-level UDP 4720 scan (request, broadcast address, timers, reply acceptance and fields), device-side responder, address entry and LAN versus remote, control connection summary. | R1 to R30 |
| [lan-discovery/kalay-search.md](lan-discovery/kalay-search.md) | Kalay LAN search (opcodes 0601 to 0604); the optional LAN-direct socket bypass is summarized here and specified in [p2p-tunnel/session.md: LAN-direct bypass](p2p-tunnel/session.md#lan-direct-bypass). | R31 to R38 |

## Open questions

- Firmware 9.75: the UDP 4720 handler of the 64-bit imager is identical in structure, strings and
  callees to firmware 9.31 (READ), and no new discovery port or listener exists. Call-for-call
  diffing of the helpers behind `tcp_client_num` and the lock and password fields shows each one
  unchanged between the two builds, the only differences being rodata and GOT layout shifts
  (READ). The key-management reader gained an internal lock around the same three-field copy in
  firmware 9.75; the fields it returns are unchanged (READ). The 32-bit scan handler and all four
  of its own field helpers are likewise a call-for-call match with firmware 9.31, except that the
  32-bit password helper's logic is unchanged but its compiled form differs (a standard-library
  move-construction the 9.31 build calls as a function is inlined in 9.75) (READ). The Kalay
  search reply builder (UDP 32761) is addressed separately; see
  [lan-discovery/kalay-search.md: Kalay LAN search: opcodes 0601 to 0604](lan-discovery/kalay-search.md#kalay-lan-search-opcodes-0601-to-0604).
  unresolved: that reply builder's packet-field construction is not traced byte for byte on
  firmware 9.75.

- iOS: the request form differs and is answered like the Android form
  ([app-scan.md: Request](lan-discovery/app-scan.md#request)); source-address rule, retries, lock
  UI, scanning in remote mode and manual address entry are unresolved. No native reply to the
  iOS form has been captured. unresolved.
- Exact serialized reply bytes: see [app-scan.md: Example](lan-discovery/app-scan.md#example).
  Optional members and model strings for each model are also unresolved.
- The full value set of `serc`, the access point's key-management mode
  ([app-scan.md: Reply fields](lan-discovery/app-scan.md#reply-fields)). Its source is READ (the AP's
  hostapd `wpa_key_mgmt` text, never written by the firmware), but the AP configuration comes
  from the base system image, which the update packages do not contain. unresolved. Re-checked for
  firmware 9.75, both builds: no binary or script in the update package writes `wpa_key_mgmt`; they
  only read it. READ.
- Reply delivery across routers and AP isolation: see
  [app-scan.md R6](lan-discovery/app-scan.md#choosing-the-broadcast-address). Delivery over
  VPN overlays is also unresolved.
- Which record wins when two hosts advertise one `sn` on iOS. unresolved.
- LAN-direct bypass success and fallback at runtime, and iOS mapping choices. Unresolved; see Q29
  in [00-overview.md: Open-question register](../00-overview.md#open-question-register).

## Appendix: How to validate on a live device (non-normative)

INFERRED; owner-run, passive first.

1. Capture at the AP or a bridge that sees both broadcast and unicast while the official app
   connects. Record UDP 4720 request bytes (source port, CRLF, id) and the full reply; tell it
   apart from UDP 32761 Kalay frames.
2. Record the selected `sn` and every TCP destination opened afterwards (see [ports.md](ports.md)).
3. In remote mode, compare a same-LAN connect with an off-LAN one: look for direct TCP to device
   application ports after the tunnel is up.
4. Sanitize serials, client ids and lock digests before sharing captures.
