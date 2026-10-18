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
  The Kalay reply construction is traced in firmware 9.75, both builds. Before the send transformation, the extended `0x0602` reply is 200 bytes with a 184-byte body: identity at 16–35, zeros at 36–51, 129 bytes of configured device information at 52–180, three zero bytes at 181–183, LE32 SDK version `0x04030603` at 184, RID8 or zeros at 188, and LE32 status at 196. The legacy reply is 184 bytes with body length 168, logged-in identity at 16–35, requester IPv4 sockaddr at 36–51, device information at 52–180 and zero padding at 181–183; it has no extended suffix. READ. Runtime identity/information values, actual reply delivery and server-side meanings remain unresolved.

- iOS: the request form differs and is answered like the Android form ([app-scan.md: Request](lan-discovery/app-scan.md#request)). No native reply to the iOS form has been captured.
- iOS app 3.4.0 constructs the UDP 4720 scan request with id 201, method scan_iscope, name iphone and the phone's current Wi-Fi IP, and sends it to the Wi-Fi broadcast address. The scanner's default repeating interval is five seconds; the traced LAN screen configures two seconds, and scanning sends once immediately on start. Stopping clears the scan cache and invalidates the timer. The receiver assigns the datagram source IP to the device record without requiring equality with a payload IP. READ for construction and scheduling, not measured packet cadence or delivery. The LAN screen's admission check requires current Wi-Fi information and rejects either checked network or local-network authorization state equal to 2; this gate does not test active remote state. Leaving that connection page stops its scan. The ordinary connection manager separately stops its scanner when its callback finds active remote state. The LAN screen configures a periodic 20-second empty-list check that stops scanning and displays a no-device state only when the displayed list is empty. Locked records display a lock and open local password verification, which checks input string length six and compares its MD5 representation with the supplied password representation before continuing with the selected record. READ for these iOS client paths. No manual address-entry path was recovered in this bounded LAN-screen trace. Address entry elsewhere, filtering beyond the inspected socket construction and actual reply delivery remain unresolved. Firmware 9.31/9.75 responder behavior remains a separate result.
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
- iOS app 3.4.0 inserts scan results into a mutable set whose model equality and hash use the serial number. The receive path inserts without replacing or merging an equal record and supplies the set's contents to the scan callback. READ. For equal nonnull serial strings, the first inserted record is retained until cache clearing, including its source-derived IP (INFERRED from set insertion and equality). The traced LAN screen filters callback records on is_verified and coalesces pending refreshes with a nominal 0.3-second dispatch delay. Its display merge replaces equal records at their existing positions and appends new records, without sorting or removing records absent from the incoming array. Its connect control retains the displayed model, saves that selected record and uses its IP for the traced connection factories. READ. Initial set-to-array order, host arrival order and actual timing remain unresolved. This app cache/display policy is separate from firmware 9.31/9.75 responder behavior.
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
