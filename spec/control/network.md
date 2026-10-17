# Network configuration

This chapter covers the control-service methods that configure the device's own networking:
the access point (AP), the Wi-Fi client ("station"), the 5 GHz band, the regulatory country,
the internet check and remote-access enrolment, plus the `Station` event. It sits on the
JSON-RPC envelope ([session-handshake.md](session-handshake.md)). The links these methods change
carry the transports below it ([../transport/ports.md](../transport/ports.md),
[../transport/lan-discovery.md](../transport/lan-discovery.md),
[../transport/p2p-tunnel/index.md](../transport/p2p-tunnel/index.md)). Related settings are in
[device-state-and-settings.md](device-state-and-settings.md).

App names: “Wi-Fi” is the access point; “2.4G Wi-Fi” and “5G Wi-Fi” pick its band; “Wi-Fi connection
area” is the regulatory country; “Station Mode” is the Wi-Fi client, which the app's “Telescope
Network” steps require (the app calls it the “bridged WLAN”; that wording does not imply a layer-2
bridge). Joining “Telescope Network” uses remote-access enrolment. Names are the English strings of
iOS app 3.4.0; links are READ (app call sites) unless marked.

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED**, **INFERRED** and
**unresolved** are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions). READ claims are
for the 64-bit imager build of firmware 9.31; the 32-bit build is "probable" unless stated.
Statements tagged "firmware 9.75" are for firmware 9.75 (app 3.4.0), 64-bit imager unless stated;
they add to the 9.31 statements, which stay as written for that firmware.

Basis: static analysis of firmware 9.31 and 9.75, their packaged network scripts, and app 3.3.2
(9.31) and 3.4.0 (9.75).

All SSIDs, keys and addresses in this chapter are placeholders. Example addresses are placeholders.

## Overview

The device runs an AP for direct connection and can also join an existing Wi-Fi network as a
station. Almost every method here runs one command of a packaged network script synchronously
and judges success from its text output. READ.

R1. A success reply means the script ran and its output did not contain the error marker
checked by that method. It does not mean the link is up. Clients MUST confirm the resulting
state with a getter (`pi_get_ap`, `pi_get_ap_channel`, `pi_station_state`). READ (device);
normative (client).

R2. Script calls have no RPC-side timeout. A client SHOULD apply its own reply timeout to every
method in this chapter. READ / INFERRED.

R3. Methods that reconfigure the radio can drop the client's own link before the reply is sent.
A client connected over the link it is changing MUST treat a lost connection as a possible
success and reconnect, then re-read state. INFERRED.

Common script errors (READ): 214 the command could not be started; 223 the command produced no
output where output is required; 207 the output contains an error marker.

## Access point

| Method | Purpose | Tier |
|---|---|---|
| [`pi_get_ap`](../../docs/control/methods/pi_get_ap.md) | Read AP name and key | B |
| [`pi_set_ap`](../../docs/control/methods/pi_set_ap.md) | Set AP name and key, restart AP | C |
| [`pi_get_ap_channel`](../../docs/control/methods/pi_get_ap_channel.md) | Read AP band, channel, frequency | B |
| [`pi_set_5g`](../../docs/control/methods/pi_set_5g.md) | Switch AP between 2.4 GHz and 5 GHz | C |
| [`set_wifi_country`](../../docs/control/methods/set_wifi_country.md) | Set regulatory country | C |

R4. `pi_get_ap` returns `{ssid, passwd}`. The key is returned in clear on firmware 9.31. Firmware
9.75 keeps the flat `{ssid, passwd}` result and replaces the value of `passwd` with an `enc1:`
token, which needs a secure-communication session ([secure-communication.md](secure-communication.md));
there is no `wifi` object (the word is only a cipher context). A connection with no active
session gets 570 instead of a result; encoding failures give 571 to 573. Errors: 214, 223, and
221 when the expected line is not found in the script output. Clients MUST treat `passwd` as a
secret. READ (device); normative (client).

R5. `pi_set_ap` accepts `[ssid, key]` or `{ssid, key}`. Non-string members, including an
explicit JSON null, give 105. The handler checks no length; the strings are formatted into a
bounded command buffer, so very long values can be truncated (this is not a validated maximum).
READ.

R6. A non-empty key shorter than 8 characters is rejected by the script, giving 204. An explicitly
empty key is skipped: the AP key is left unchanged and the call can succeed. READ (firmware 9.31).

R6a. Firmware 9.75: `key` is an `enc1:` token that the device decodes with the connection's
crypto session ([secure-communication.md](secure-communication.md)); the `ssid` stays plain. A
decode failure or a missing session returns the wrapper code 570 to 573 (not 105); a non-string
member still gives 105. The device additionally validates the text of the SSID and key and
returns 102 on failure, with an SSID limit of 32 bytes and a key limit of 63 bytes. READ for the
codes and limits. A success also emits the `ap_changed` setting notification (R8).

R6b. The key-length rule, confirmed from firmware 9.75 disassembly of both imager builds: a
decoded key is accepted when it is empty or 8 to 63 bytes; a decoded key of 1 to 7 bytes is
rejected with 102. The check uses an unsigned-subtraction idiom (`length - 1 <= 6`) to test the
1-to-7 range in one comparison. An empty decoded key is still handled as in R6: the AP key is
left unchanged. The text validator behind 102 also rejects a NUL, CR or LF byte in `ssid` or
`key`; it applies no other charset restriction. READ (both builds, structurally identical).

R6c. If the request omits `key` entirely (as opposed to sending an empty string or an `enc1:`
token), the handler never reaches the decode step: it skips both the crypto-session check and the
102 length validation and leaves the AP key unchanged, the same outcome as an empty key. R6a's "a
client that cannot establish a session cannot change the AP name or key on 9.75" therefore holds
only when the request includes a `key` member; a client with no session MAY still change `ssid`
alone by omitting `key`. READ.

R6d. Errors seen across the `pi_set_ap` path: 105 (non-string `ssid`/`key`, including an explicit
JSON null), 102 (key or SSID text invalid, including the 1-to-7-byte case of R6b), 570 to 573
(crypto session missing or decode failure, R6a), 214 (the restart script could not be started),
207 (the SSID-apply step's script output contained the text "error"), 204 (the key-apply step's
output contained both "error" and "too short"; reachable only for a non-empty argument shorter
than 8 bytes that reaches this downstream script check rather than the RPC-level 102 check).
Empty output from either apply step is treated as success, with no fresh 223 raised for it; the
AP-restart step's own success is not checked against the restart script's exit code. READ.

R6e. A defect, not a documented contract: when the key-apply script's output contains "error" but
not "too short", the native helper returns failure without assigning a fresh error code, so the
handler can serialize whatever numeric error code a thread-local variable last held from an
unrelated prior operation — there is no closed, input-independent set of codes for this path.
READ. Clients MUST NOT treat a `pi_set_ap` error code as proof of which validation step failed
unless it is one of 105, 102, 570 to 573, or 214.

R7. After writing, the device stops the AP daemon, waits about 1 s and starts it again. Clients
connected through the AP will lose the link. READ (restart); INFERRED (link loss).

R8. On NFC-capable models the first change of the AP name sets the persistent `ap_changed` flag
and can send a [`Setting`](../../docs/control/events/Setting.md) event carrying `ap_changed`. An
AP name change is also reported to the device's remote-access component. READ.

R9. A request without `ssid` has no established clean success path. Clients MUST send `ssid`.
READ (unestablished path); normative (client).

R10. `pi_get_ap_channel` returns `{is_5g, channel, freq}`. `freq` is in MHz; `is_5g` is true when
5000 <= freq < 6000. Errors 214, 223, 207. READ.

R11. `pi_set_5g` accepts a boolean, `[boolean]` or `{is5g: boolean}`. Integers are rejected with
106. The device reads the current channel before running the band switch. READ.

R12. If the requested band is already active, the device appends a success result but still
runs the script, so the reply can contain duplicate `code`/`result` members. Clients MUST
tolerate a duplicate-member reply and SHOULD confirm with `pi_get_ap_channel`. READ (device).

R13. `set_wifi_country` accepts a string, `[string]` or `{country: string}`; otherwise 105. The
value is not validated: it is formatted unquoted into a 255-byte shell command line (longer
text is truncated), validation is left to the wireless driver, and the outcome is not checked.
Only 214 is reported. READ. The change runs in the background after the reply and restarts the
access point; an empty string resets the country to the factory default; a value equal to the
current one does nothing. READ. Because the value reaches a shell, whitespace splits it and
shell metacharacters are interpreted. INFERRED. A client MUST send only an uppercase ISO 3166-1
alpha-2 code. A stand-in device SHOULD reject anything else.

The current country is reported as `wifi_country` by `get_setting`. READ.

## Station (Wi-Fi client)

| Method | Purpose | Tier |
|---|---|---|
| [`pi_station_scan`](../../docs/control/methods/pi_station_scan.md) | Active scan | C |
| [`pi_station_list`](../../docs/control/methods/pi_station_list.md) | List saved networks | C |
| [`pi_station_set`](../../docs/control/methods/pi_station_set.md) | Save and join a network | C |
| [`pi_station_select`](../../docs/control/methods/pi_station_select.md) | Select a saved network | C |
| [`pi_station_remove`](../../docs/control/methods/pi_station_remove.md) | Delete a saved network | C |
| [`pi_station_open`](../../docs/control/methods/pi_station_open.md) / [`pi_station_close`](../../docs/control/methods/pi_station_close.md) | Enable or disable station mode | C |
| [`pi_station_auto_connect`](../../docs/control/methods/pi_station_auto_connect.md) | Let the script pick a saved network | C |
| [`pi_station_state`](../../docs/control/methods/pi_station_state.md) | Read connection state | B |

R14. `pi_station_scan` starts an active radio scan, then reads results. Each item has `freq`,
`sig_lev`, `flags` and `ssid`. The packaged script keeps entries with signal level >= -80 and
sorts them strongest first; both builds' scripts do the same. READ. The device then:

1. drops entries with an empty SSID;
2. keeps only the first (strongest) entry for each SSID within a band (5 GHz means a frequency
   above 4999 MHz);
3. keeps only entries in the same band as its own access point, so networks in the other band
   never appear. If the access-point band cannot be read, only 5 GHz entries are kept.

READ (steps); INFERRED (the fallback's effect). Errors 214, 223. READ. `freq` is in MHz and
`sig_lev` in dBm. READ. A client MUST NOT treat a missing SSID as proof that the network is
absent.

R15. `pi_station_scan` and `pi_station_list` take an optional `ret_obj` (boolean or integer). When
true the array is wrapped as `{value: [...]}`. A malformed value is treated as false. READ.

R16. `pi_station_list` can ask the Wi-Fi supplicant to reconfigure before listing on some
models. It is therefore not observation-safe. READ.

R17. `pi_station_set` takes an object or `[object]`, optionally wrapped in `para` (a non-object
`para` gives 107). Members: `ssid` (string,
required, non-empty), `psk` (string, default empty), `timeout_sec` (integer, default 10),
`hidden` (boolean or integer, default false). A missing or empty `ssid` gives 105. Type errors:
107, 105, 104, 106. READ (firmware 9.31).

R17a. Firmware 9.75: `psk` is read from the object selected by `para` and holds an `enc1:` token
([secure-communication.md](secure-communication.md)), not plaintext. The handler checks that a
crypto session is active and returns 570 if not, even when `psk` is omitted (R17b); a token that
cannot be decoded returns the wrapper code 571 to 573. There is no `wifi` object. READ.

R17b. The member list and defaults of R17 are confirmed unchanged for 9.75 in both builds: `ssid`
(string, required, non-empty), `psk` (optional, default empty once decoded), `timeout_sec`
(integer, default 10), `hidden` (boolean or integer, default false); unrecognised members are
skipped. A crypto session is required for the call even when `psk` is absent or decodes to empty.
READ (both builds, structurally identical).

R17c. The decoded `psk` length rule is 0 to 64 bytes, with no minimum length and no special case
at exactly 64 bytes — unlike `pi_set_ap`'s key (R6b), which rejects 1 to 7 bytes. A client or
stand-in MUST NOT copy the access point's 8-to-63 key rule onto the station `psk`. READ (both
builds).

R17d. An empty decoded `psk` configures the network as an open (unauthenticated) network
(`key_mgmt=NONE`); this is a genuinely supported configuration, not an error. A non-empty `psk`
is passed to a WPA-passphrase derivation step, or to a separate path selected by a `[WEP]` flag
in the saved network entry. Whether the external passphrase/supplicant tooling itself enforces
any length limit on the 1-to-7-byte or 64-byte edge cases was not established by static reading
(no such binary was found in the extracted packages). unresolved.

R17e. The trigger for 104 is a present-but-non-integer `timeout_sec`. Full error set: 107 (`para`
present but not an object), 105 (missing or non-string `ssid`, or `psk` present but not a string),
104 (`timeout_sec` present and not an integer), 106 (`hidden` present and not a boolean or integer),
102 (decoded `psk` length invalid), 570 to 573 (crypto session or decode failure), 214 (script could
not be started), 207 (script output contained "error"), 209 (`timeout_sec` <= 0, checked only after
the configuration write, as in R18), 212 (the connection check thread failed to start). READ (both
builds).

R17f. Because the request is ordinary JSON, an embedded NUL byte in `ssid` truncates the value at
the NUL for a JSON parser that represents strings as C strings internally; a client MUST NOT rely
on bytes after an embedded NUL being preserved. READ.

R18. `pi_station_set` writes the configuration first and then validates `timeout_sec`. A value
<= 0 gives 209 after the configuration has already changed. Nothing is rolled back. Clients
MUST send a positive `timeout_sec`. READ (device); normative (client).

R19. On success `pi_station_set` replaces any previous check thread with a new one that watches
the connection for `timeout_sec` seconds, and replies at once. Errors 214, 207, 212. READ.

R20. The connection outcome is learned by polling `pi_station_state` or from the `Station`
event ([Station event](#station-event)). The check that `pi_station_set` starts is the only producer of `Station`.
It tests the connection about once a second until `timeout_sec` has passed. On failure (timeout,
an error from the check, or an address in 10.0.0.x) the device deletes the saved network it was
trying to join and then sends `Station` `fail`. A newer `pi_station_set` stops the previous check
without any event for it. READ. A client MUST re-send the credentials to retry and MUST NOT
assume a failed network is still saved.

R20a. Firmware 9.75, both builds: the packaged network script's connection test now also requires
the supplicant state to be `COMPLETED`, after the SSID and address tests. A link that has an
address but has not finished authenticating no longer counts as connected, so a `Station`
`complete` or a `pi_station_state` with `server:true` needs the finished association. READ.

R21. `pi_station_select` takes `ssid` as a string, `[string]` or `{ssid}`. It selects and saves;
success does not mean connected. Errors 105, 214, 207. READ.

R22. `pi_station_remove` takes `ssid` as a string, `[string]` or `{ssid}`. Empty string gives 217; non-string gives 105; error text in
the output gives 207. It may reconfigure the interface and drop the station link when the
removed network was active. Success does not prove removal. READ.

R23. `pi_station_open` and `pi_station_close` read no params and turn station mode on or off.
Errors 214, 207. READ.

R24. `pi_station_auto_connect` reads no params and runs the script's automatic selection. Empty
output counts as success. It can change connectivity and drop the caller's link. READ.

R25. `pi_station_state` returns `{server: boolean}`. When `server` is true it adds `freq`
(integer, MHz INFERRED), `ip`, `ssid`, `gateway`, `netmask` (strings), `sig_lev` (integer,
dBm INFERRED) and `key_mgmt` (string). It never returns a key. Empty script output yields
`server:false`. Error 214. `server` reflects whether the supplicant reports itself running,
not that the connection is complete; clients SHOULD also check `ip`. READ (device); normative
(client).

The same object appears as `station` in `get_device_state`. READ.

Example (synthetic):

```
{"id":12,"method":"pi_station_state","result":{"server":true,"freq":2437,
 "ip":"<device-address>","ssid":"<ssid>","gateway":"<gateway-address>",
 "netmask":"<netmask>","sig_lev":-55,"key_mgmt":"WPA-PSK"},"code":0}
```

### Saved-network listing details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`pi_station_list`](../../docs/control/methods/pi_station_list.md) lists Wi-Fi networks for
the device's station interface. They are the networks saved in the device's Wi-Fi configuration,
not scan results; `hidden` reflects whether a saved network is set up for hidden-SSID probing.
READ (64-bit build; the 32-bit network script lacks the detailed listing action, so only plain
names are expected there, INFERRED). With `ret_obj` false or absent the result is an array of
network names or `{ssid, hidden}` objects; with `ret_obj` true it is wrapped as `{value: array}`.
Errors 214, 223. READ. On models other than the Plus and Mini it first makes the Wi-Fi
supplicant reload its configuration, which can briefly disturb an active station link, so it is
not a passive read. READ.

## Station event

R26. [`Station`](../../docs/control/events/Station.md) follows a station connection attempt
started by `pi_station_set` (R20).
States are `complete` and `fail`. On `complete` the payload has a `station` object with the
shape of R25. On `fail` it carries `code` and `error` when a code was supplied. READ.

Typical flow:

```
client                                 device
  | pi_station_set {ssid,psk,timeout_sec}|
  |------------------------------------->|  write config, start check thread
  |  {result:0,code:0}                   |
  |<-------------------------------------|
  |  ... up to timeout_sec ...           |
  |  {Event:"Station",state:"complete",  |
  |   station:{server:true,...}}         |
  |<-------------------------------------|  (or state:"fail")
```

R27. A client MUST NOT assume the event arrives; it SHOULD poll `pi_station_state` after
`timeout_sec` if no event was seen. INFERRED.

## Internet check

R28. [`check_internet`](../../docs/control/methods/check_internet.md) returns `{connected:
boolean}`. No connectivity is a success reply with `connected:false`. READ.

R29. `timeout_sec` is type-checked (104 if not an integer) but not used. READ. The device
first runs an NTP sync bounded at 4 s (R30), then one reachability probe bounded at 4 s. Probes
rotate among a ping of a public DNS address, a ping of a vendor cloud host and an HTTPS request
to a vendor endpoint. If NTP succeeded but the probe failed, one more probe is made on the next
target. READ. The worst case is therefore about 12 s plus process start-up. INFERRED. A client
SHOULD allow at least 15 s before timing out.

R30. Before checking connectivity the device tries an NTP time sync that can set the system
clock (4-second command timeout). The call is therefore tier C. See
[time-and-location.md](time-and-location.md). READ.

R30a. Firmware 9.75, both builds: `check_internet` gained no crypto-session requirement (unlike
the Wi-Fi configuration handlers above) and no new return field; it still replies only
`{connected: boolean}` (R28). The 64-bit build's wrapper function grew from 640 to 668 bytes
between 9.31 and 9.75, but the growth is compiler codegen (an inline literal construction
replacing a string-constructor call), not a behavioural change. READ.

R30b. The rotation of R29 cycles through exactly three probe targets, selected by an index
modulo 3: index 0 issues an HTTPS request to a vendor endpoint and treats output containing
`ret=200` as success; index 1 pings a vendor cloud host; index 2 pings a public DNS address; for
both ping targets, success is output containing `ret=0`. READ.

R30c. Between firmware 9.31 and 9.75 the shell command text changed: 9.31 runs the NTP sync and
each ping as `timeout 4s sudo sntp ...` / `timeout 4s sudo ping ...`; 9.75 runs them as
`sudo timeout 4s sntp ...` / `sudo timeout 4s ping ...` — `sudo` and `timeout` swap order. The
4-second budget itself (R30, R24 convention) is unchanged, but it now wraps a different scope of
the privilege-elevation sequence than before. INFERRED consequence (read from the command text,
not timed on a running device). The other numeric budgets (NTP and probe timeouts at 4 s, ping
wait 3 s, HTTPS connect/max-time 3 s) are unchanged. READ.

R30d. All of R6a to R6e, R17a to R17f and R30a to R30c above hold identically in the 32-bit
imager build; no 32-bit-specific schema or validation difference was found for `pi_set_ap`,
`pi_station_set` or `check_internet`. READ.

R30e. Firmware 9.75, 64-bit imager: the same NTP-sync-then-probe mechanism (R29-R30b) also runs
on the device's own initiative, independent of the `check_internet` RPC, from at least two
background workers: one that also performs periodic Pi-temperature housekeeping, which gates an
attempt to re-establish the remote-access enrolment of [Remote-access enrolment](#remote-access-enrolment) behind a
successful check; and one in the photometry pipeline, which gates a network-dependent step of its
own processing and reports an error and aborts that step on failure. Both share the same
rotating probe-target index as the RPC path (R30b), so a self-triggered check can land on any of
the three probe targets depending on how many times the mechanism has run in total, counting both
RPC-triggered and self-triggered calls. Unlike the RPC path, neither self-triggered caller gets
the extra retry-on-failure of R29: each makes exactly one probe per invocation. READ. The
Pi-temperature-housekeeping worker runs as its own background loop that sleeps 1 s between
iterations (three separate sleep points in the loop, each 1 s); the self-triggered internet check
and rejoin attempt are reached from inside that loop, but whether they run on every iteration or
only on some of them was not established. READ (loop cadence); unresolved (that detail). The
photometry worker's own loop body has no comparable sleep call, so its trigger condition and any
periodic interval remain unresolved.

## Remote-access enrolment

These methods enrol the device with the vendor's relay service, which carries the P2P tunnel
described in [../transport/p2p-tunnel/index.md](../transport/p2p-tunnel/index.md). READ.

R31. [`remote_join`](../../docs/control/methods/remote_join.md) requires string members `host`,
`productKey`, `deviceName`, `deviceSecret` and `port` (a string, not a number), and optional
integer `timeout_sec` (default 2, seconds). A client obtains these values from the vendor's
account service; they are credentials and MUST NOT be logged. READ (params); INFERRED (source).

R32. Any parse failure in `remote_join` gives 259, whose message text is "stack is already
running". The message is misleading; clients MUST rely on the code. A wrong `timeout_sec` type
gives 104; a join failure gives 207. READ.

R33. On success the device stores the request for later reuse and sends a `Setting` event with
`remote_joined:true`. READ. Firmware 9.75: the join also reports the OTA version information
(the manifest-aware main version and module list of [maintenance.md](maintenance.md)) instead of
the legacy firmware version alone; whether this changes anything on the wire is unresolved. READ
(the call).

R34. [`remote_disjoin`](../../docs/control/methods/remote_disjoin.md) removes the stored join
and sends `Setting` with `remote_joined:false` on both success and failure. Error 207. READ.
Firmware 9.75: leaving the remote network also disconnects the device's cloud messaging client; the
wire effect is unresolved. READ (the call).

R35. [`remote_disconnect`](../../docs/control/methods/remote_disconnect.md) clears auto-connect
and stops the tunnel server but keeps the stored join. Error 207. READ.

R36. [`remote_rebind_device_user`](../../docs/control/methods/remote_rebind_device_user.md)
requires an object with string `userId`. It always replies 0 once the report helper returns;
success does not show the rebind completed. Errors 107, 105. READ.

### Firmware 9.75 network-script comparison

R14 (network configuration). Firmware 9.75 package scripts (READ):
- Both builds: the network status script's connectivity check now also requires
  `wpa_state=COMPLETED` in the output of the `wpa_cli status` call it already made; this is the
  only difference from firmware 9.31 in that script (READ). There is no
  access-point or key-management change in any script.

## Open questions

- The unit of the signal level in `pi_station_state` (dBm INFERRED; the driver's number is
  passed through). unresolved.
- Firmware 9.75: whether the external WPA/WEP passphrase or supplicant tooling itself enforces
  any length limit on a 1-to-7-byte or exactly-64-byte station `psk` (R17d); which stale error
  code `pi_set_ap`'s key-apply path can propagate when its script reports "error" without "too
  short" (R6e). unresolved.

## Appendix: Validating on a live device (non-normative)

- `pi_get_ap_channel` and `pi_station_state` are the low-impact reads.
- Avoid `pi_station_scan`, `pi_station_list`, `pi_set_ap` and `pi_set_5g` over the link they
  affect; use a wired or second link if available.
