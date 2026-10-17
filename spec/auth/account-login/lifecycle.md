# Account login: storage, token lifecycle, timing and errors

Scope: what happens to the account token after login: storage, startup, source identifier, 401-driven renewal on the account client, token-expired handling on the remote client, logout, timeouts, retries and error mapping. Token issuance is in [login.md](login.md); the remote layer that also sends the token is in [cloud-auth.md](../cloud-auth.md).

Part of [Account login](../account-login.md): [interactive login](login.md) | [endpoint catalogue](endpoints.md) | [storage, token lifecycle and errors](lifecycle.md). [Boundaries and open questions](boundaries.md). Requirement numbers (R1..) are shared across these files; conventions and labels are in [the index: Conventions](../account-login.md#conventions).

## Storage, startup and source identifier

R37. Persistent account store (one key-value file, not encrypted by the app). READ.

| Key | Content | Default |
|---|---|---|
| `api_token` | last access token | `""` |
| `login_username` | prepared username (see R34) | `""` |
| `login_password` | prepared password, plaintext | `""` |
| `user_id` | profile `id` | `""` |

A client SHOULD keep the password, if it stores one at all, in platform-protected storage.
INFERRED (the official app does not).

R38. At application startup the application object's constructor copies the stored token into
the in-memory session token. Separately, `loginStatus` is initialized from "stored token is
non-empty" when the status holder is first loaded. Neither step checks expiry or makes a network
request. READ.

R39. Source identifier (`srcId`). A second, separate store holds `device_uuid`. At startup, if
it is absent or empty, the app writes a fresh random UUID string (`UUID.randomUUID()`, canonical
8-4-4-4-12 form, INFERRED). A non-empty value is never regenerated, validated or derived from
account, token, telescope or hardware ids. Logout never clears it. READ. This value is sent as
`srcId` on the remote online-link request ([cloud-auth.md](../cloud-auth.md)). READ.

R39a. Backup and storage reset. The store is a file under the app's private files directory.
The manifest allows backup and names backup and data-extraction rule files that contain no
include or exclude rules. There is no custom backup agent. READ (app 3.3.2). Under the
platform's default backup rules, INFERRED:
- A cloud restore or a device-to-device transfer to a new install carries the same `device_uuid`
  over, so two installs can share one `srcId`.
- Clearing the app's storage, or uninstalling without a restore, removes it, and the next start
  writes a new random value.
- A backup skipped by the platform (for example over its size quota) restores nothing, which
  also leads to a new value.

R40. Login requests and account headers never carry `srcId`, a telescope serial, an IOTC UID or a
device-binding proof. READ. The mobile pattern used by automatic re-login is
`^((13[0-9])|(14[579])|(15[0-35-9])|(16[2567])|(17[0-35-8])|(18[0-9])|(19[0-35-9]))\d{8}$`. READ.

R41. A client SHOULD create `srcId` once per installation and reuse it across restarts, logins
and logouts. INFERRED. Startup creation is read-then-write, not atomic; two first-start processes
could race. This is an implementation concern, not a protocol question.

R42. Token hand-off: the remote client reads the same stored `api_token` and sends it verbatim as
`Authorization` (profile C). There is no token exchange between the account and remote layers.
READ. The stored token is read again for every remote request, and the header is omitted when
it is empty, so a token installed by the account layer's credential replay ([Account client: 401-driven credential replay](#account-client-401-driven-credential-replay) of
[lifecycle.md](lifecycle.md#account-client-401-driven-credential-replay)) is used by the next
remote request without any hand-off. READ.

## Token renewal, expiry and logout

### Account client: 401-driven credential replay

Trigger: any HTTP 401 on an account-API call (profile A). No timer, and neither `accessExpire`
nor `refreshAfter`, starts a renewal. READ. Let *n* = 1 + the number of earlier responses in the
current follow-up chain. READ.

| State / event | Guard | Action | Next |
|---|---|---|---|
| WAIT, request gets 401 | saved username or password empty | clear token (store and memory), user, `user_id`, password; `loginStatus = false` | LOGGED_OUT (request fails) |
| WAIT, request gets 401 | *n* >= 3 | same clearing (username and `srcId` kept) | LOGGED_OUT |
| WAIT, request gets 401 | *n* < 3, credentials present | synchronous `POST /v1/user/login`, profile B, `category` 0 | RELOGIN |
| RELOGIN | HTTP 2xx | set session token and stored token from `data.accessToken`; no other checks; no profile fetch | REPLAY |
| RELOGIN | HTTP non-2xx | keep old token | REPLAY |
| RELOGIN | exception | ignore | REPLAY |
| REPLAY | - | rebuild the original request, **replacing** both authorization headers with the current session token; resend, if header construction succeeds (that step is outside the re-login exception guard) | WAIT |
| WAIT | non-401 response | deliver it | done |

All transitions READ. Consequences, INFERRED: at most 2 re-logins and 3 attempts of the original
request per chain; a failed re-login replays the stale token; earlier redirects consume the
budget.

R43. The re-login uses a separate plain HTTP client: no application headers, 10 s connect/read/
write timeouts, no recursion into this mechanism, no locking, no coalescing of concurrent
renewals, no delay or backoff. READ. This is password replay, not a refresh-token grant.

R43a. Concurrency and process restarts. The renewer is not synchronized. The in-memory session
token is a plain process-wide value, separate from the stored `api_token`, which lives in a store
shared across processes. The app runs several OS processes: the main UI process plus device,
map, proxy and upload processes. Each process copies the stored token into its own session
token when it starts. A successful re-login writes the stored token immediately after the 2xx
reply, before the replay. The remote client reads the stored token again for every request
(R42). READ (app 3.3.2). Consequences, INFERRED:
- Concurrent 401 chains each re-login independently, and the token stored last wins.
- One chain's clearing (*n* >= 3 or missing credentials) can wipe a token that another chain has
  just installed.
- A re-login in one process updates the shared store but not the session token of other
  processes. Those keep sending the old token on account calls until their own 401 starts their
  own re-login.
- A restart, including a system re-creation of the process, reloads the stored token. A renewal
  whose reply was stored survives the restart. A restart between the 401 and that reply leaves
  the old token in place.

A remote 401 before the profile is installed is the "user-service id unset" row of [Remote client: token-expired event](#remote-client-token-expired-event).

R44. The app's renewer can store a null token if a 2xx reply lacks `accessToken` (INFERRED from a
missing null check, READ). A client MUST apply R23 to re-login replies too.

R45. A client that stores the password MAY implement this replay. It SHOULD bound attempts as
above, SHOULD serialize concurrent renewals, and MUST NOT retry on wrong-password answers.
INFERRED (policy).

### Remote client: token-expired event

R46. The remote/cloud client (profile C) has **no** renewer installed in normal startup. READ.

| State | Event | Action | Next |
|---|---|---|---|
| ACTIVE | HTTP 401 on a remote call | emit TOKEN_EXPIRED; return an API error with HTTP status; call user-service logout; build (but do not open) the login route | EXPIRED |
| EXPIRED, user-service id unset | - | clear service user only; no listeners; stored credentials kept | EXPIRED |
| EXPIRED, user-service id set | - | clear service user and id; notify logout listeners | LISTENERS |
| LISTENERS, account logout listener registered, session token null | - | listener returns without cleanup | EXPIRED |
| LISTENERS, listener registered, session token non-null (incl. `""`) | - | clear stored token, `user_id`, password, session token, profile; `loginStatus = false` | LOGGED_OUT |

All rows READ. The account logout listener is registered when the home screen first initializes
its SDK, during the home screen's creation. READ. Application start-up and the splash screen send
no remote-API request: start-up only configures the remote client, and the splash screen waits,
shows the policy dialog if needed and opens the home screen. Remote-API requests start from the
home screen or later screens. READ (app 3.3.2). In a normal launch the listener is therefore in
place before any remote reply can arrive. INFERRED: the 401 event is raised on a network thread
and nothing orders it against registration explicitly, and if the system recreates the process
directly on a later screen without the home screen, the listener is not registered and a remote
401 clears only the user-service state (second and third rows).

The remote 401 handling does not compare the token the failed request carried with the current
session token: a 401 for an older token, arriving after [Account client: 401-driven credential replay](#account-client-401-driven-credential-replay) has installed a newer one, clears
the newer one too. The two layers share no lock. READ. Whether the server treats such a 401 as
ending the account session or only the older token is unresolved (server-side).

R47. A client SHOULD treat HTTP 401 from the remote API host as "re-authentication needed" and
SHOULD NOT assume the remote request was silently renewed. INFERRED. Automatic renewal there is
new behaviour and SHOULD be documented as such.

### Explicit logout

R48. Logout is local only: no logout or revoke request is sent. Saved username and `srcId` are
kept. READ. Three logout bodies exist with different guards. READ.

| Path | Guard | Clears |
|---|---|---|
| account logout service (also the 7.2 listener) | returns early if session token is null | stored token, `user_id`, password, session token, profile; guide flags; `loginStatus = false` |
| settings screen logout | none | same, without guide flags |
| embedded web page `logoff` bridge call | none | same plus guide flags; navigates |

No logout path sends `remote_disjoin` or `remote_disconnect`. The logout action of the account
(personal information) screen first disconnects an open remote session, which sends the relay
stop request when a `conId` is known; the `logoff` bridge call and the 7.2 listener do not.
READ (app 3.3.2).

R49. Entering the login screen clears the stored token but not the in-memory session token, which
can still be sent until another transition. READ.

R50. A client SHOULD clear all account credentials on explicit logout unconditionally. INFERRED
(policy; differs from the official null guard). Local logout does not show server-side revocation
or teardown of an active relay session; explicit relay teardown is specified in
[cloud-auth.md](../cloud-auth.md). INFERRED.

## Timing

| Activity | Value | Label |
|---|---|---|
| Account API calls (profile A) | connect 70 s, write 60 s, read 120 s; retry on connection failure | READ |
| Automatic re-login (profile B) | connect/read/write 10 s each; no call timeout | READ |
| Remote API calls (profile C) | connect 70 s, write 60 s, read 120 s; retry on connection failure | READ |
| Alternative account JSON client (not used for login) | connect 45 s | READ |
| 401 replay chain | stop at *n* >= 3; no sleep | READ |
| HTTP follow-ups (redirects etc.) | at most 20 | READ |
| Verification-code resend countdown | 60 s, 1 s ticks (UI only) | READ |
| Proactive token refresh | none | READ |

R51. Connect, read and write limits are per phase; they do not add up to an end-to-end deadline.
The 60 s countdown says nothing about code lifetime on the server. INFERRED.

R52. Stack-level retries (READ): connection recovery when allowed; one retry on HTTP 408 if the
body is replayable and `Retry-After` is absent or 0; one retry on HTTP 503 only if `Retry-After`
is 0 (absent or non-numeric counts as "never"); HTTP 421 handled by the stack. None of these
sleep. They are not account lockout or password retry rules.

## Errors

HTTP 401 means credentials were missing or refused (RFC 9110 §15.5.2); it does not by itself mean
"expired". The app's TOKEN_EXPIRED label is its own interpretation.

R53. Account client error mapping. The HTTP status is what the app acts on; the envelope `code`
in error bodies is parsed and then discarded, `msg` is kept. READ.

| Event | App handling | Label |
|---|---|---|
| HTTP 200/201/204 | success callback (login installs a token only on 200) | READ |
| HTTP 401 after 7.1 | stored token empty: "network abnormal"; else "session expired" and go to login | READ |
| HTTP 403 | "session expired" text; status kept | READ |
| HTTP 404 | no server message used | READ |
| other non-2xx | read `msg` from JSON body if possible | READ |
| network or parse exception | "network abnormal" (login); completion (profile, R25) | READ |
| remote API HTTP 400 with body | parse `{code, msg}` envelope and expose both | READ |
| remote API HTTP 401 | [Remote client: token-expired event](#remote-client-token-expired-event) | READ |
| remote API unknown host | UNKNOWN_HOST event | READ |

R54. Envelope codes for bad credentials, locked or disabled account, region rejection, expired
verification code and rate limiting are unresolved (server-side). A client MUST NOT map HTTP 401/403 to a
specific cause, and SHOULD surface unknown `code`/`msg` pairs unchanged. INFERRED.

R55. A client MUST NOT retry a login that failed with a non-transport error automatically, to
avoid triggering any server lockout. INFERRED (policy).
