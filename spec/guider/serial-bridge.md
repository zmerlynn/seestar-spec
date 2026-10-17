# Serial bridge (ser2net)

This chapter covers the guider process's raw serial bridge on TCP 4030 and the two-method
control table (`set_settings`, `disconnect`, served on TCP 4040) that configures it. Below it sits the mount
serial device; above it, a client that wants to talk to the mount directly instead of through
the guider's `scope_*` commands. The guider's JSON server is in [index.md](index.md); the
process overview is in [../00-overview.md](../00-overview.md).

## Conventions

Labels, RFC 2119 keywords and the request/reply envelope are as in
[index.md: Conventions](index.md#conventions) and [Replies](index.md#replies). Basis:
static analysis of firmware 9.31 (guider ELF, 64-bit build). Nothing here was observed on a
device.

## Raw byte socket

R1. The guider starts a ser2net-style listener on TCP 4030 at startup. It binds all
interfaces. READ.

R1a. The bridge accepts a 4030 client only while a client from the same source IP is verified on
the control server (TCP 4040, [Control table](#control-table)), or while factory mode is on. Otherwise it rejects the
connection at accept and closes it. When that IP no longer has a verified 4040 client, the
bridge closes its 4030 connections. READ. A client MUST therefore connect and verify on 4040
before opening 4030, and keep the 4040 connection open while it uses the bridge. INFERRED.

R2. Bytes from the client are written to the opened serial file descriptor, and bytes read
from the serial device are written back to the client. INFERRED (ser2net role and reader
loop); there is no framing, header or acknowledgement on this socket in the evidence.

R3. (See also [mount-serial-commands.md R2](mount-serial-commands.md#transport-and-framing): the guider's own mount driver opens the line at 115200 baud.) The bridge uses the same serial link as the guider's mount driver, chosen by the guider's
device auto-selection (by USB vendor and product id); there is no fixed device path. READ. The
default line settings are 9600 baud, 8 data bits, no parity and 1 stop bit, unless stored
settings differ. READ. Several 4030 clients may connect. All client bytes go to the one line,
all line bytes go to every client, and writes interleave at write-call granularity with each
other and with the guider's own mount commands. READ. A client SHOULD NOT use the bridge while
the guider is driving the mount (slew, guide, park). INFERRED.

## Control table

A separate command table, distinct from the 4400 command table, holds two methods. READ.
The table belongs to the guider's ser2net control server, separate from the 4400 server.
READ. That server listens on TCP 4040, on all interfaces; it is the only 4040 listener in the
firmware. 4040 is in the client-verification port set. READ. The imager never relays them
(see [index.md R6](index.md#command-relay)). READ.

### set_settings

```text
{"id":1,"method":"set_settings","params":{"setting":{"baudrate":9600,"word_size":8,"stop_bits":1,"parity":0}}}
```

The shape is READ; the values are the defaults (R3). The accepted values are in R5.

R4. `params` MUST be an object, or an array whose first element is such an object, with a
member `setting` that is an object. Otherwise the reply is error 107. READ.

R5. `setting` members `baudrate`, `word_size`, `stop_bits` and `parity` are read as integers;
each absent or non-integer member defaults to -1. A string `parity` is ignored (treated as
absent). READ. A negative value (the -1 default), or a value equal to the current one, leaves
that setting unchanged. READ. `baudrate` must be a standard POSIX rate from 50 to 230400,
`word_size` 5 to 8, `stop_bits` 1 or 2, and `parity` 0 (none), 1 or 2. READ / INFERRED (1 =
odd, 2 = even). An unsupported value makes the reopen fail. READ. Changed settings take effect
by reopening the device and persist across restarts. READ.

R6. The reply to `set_settings` is result 0 whenever the shape check passes, even if the
settings could not be applied; 107 is its only error. A failure is only logged. READ. A client
MUST NOT treat result 0 as proof that the line settings changed.

Card: [set_settings](../../docs/serial-bridge/methods/set_settings.md).

### disconnect

R7. `disconnect` reads no params. It stops the bridge reader and closes the serial
descriptor. The reply is always result 0. READ.

R8. After `disconnect` the serial link reopens automatically on the next write, from a 4030
client or from the guider's own mount commands, using the stored settings. Sending bytes on
4030 also restarts the reader. READ. If the reopen fails, the bytes are dropped and only the
log records it. READ. A client MUST NOT assume the bridge, or the guider's own mount link, is
usable after `disconnect` until traffic has flowed again. INFERRED.

Card: [disconnect](../../docs/serial-bridge/methods/disconnect.md).

## Open questions

- Dispatcher-level errors (missing id, unknown method) for this table; one card lists rows
  that are not established for the guider server.
- Which of `parity` 1 and 2 is odd and which is even (R5, INFERRED).
- Whether anything beyond write-call interleaving keeps several 4030 clients and the guider's
  mount commands from corrupting each other's exchanges (R3).
