# Updater: Legacy update flow

Basis: static analysis of firmware 9.75, 64-bit and 32-bit builds; the 32-bit updater was compared by strings and symbols only. Nothing here was validated on a device.

## Legacy update flow in 64-bit firmware 9.75

R13. The 64-bit legacy update script takes a lock file so only one legacy update runs at a time:
a second run prints that an update is already running and exits with status 1; if the locking tool
is missing the script exits. The lock is not inherited by the daemons the update script restarts.
READ (64-bit; the 32-bit copy of this script is unchanged).

R13a. After unpacking, the script checks whether the new update package declares a cleanup protocol.
If it does, the package script runs in a subshell that waits up to 15 s for a monitor-done marker
file written by the updater, then removes the package and work directories (only the two expected
directories; it refuses other paths) and exits with the package script's status. If the package does
not declare it, the script logs that post-cleanup is skipped. A failed unpack now cleans the package
directory. READ.

R13b. Firmware 9.75: the 64-bit updater gains matching code that takes and releases the lock, writes
the monitor-done marker and clears the legacy update directories (for the S30 Plus class the
directory is `/etc/zwo/update`, otherwise `/tmp/zwo/update`). READ. The 32-bit updater has none of
the lock, marker or path strings (INFERRED from absence). The lock is taken only inside the shared
receive preparation and released before it returns, so it covers the directory clear and receive
reservation, not the receive or install; the marker is written on every terminal path of the update
status poll, and a failed write ends it with code 207 ([index.md
R5b2](index.md#legacy-upload-flow-begin_recv)). Who consumes the marker besides the update script is
unresolved.

