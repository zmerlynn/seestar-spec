# Account login and token lifecycle

This chapter covers the ZWO account layer: how the companion app turns an email (or mobile
number) and password into an opaque access token over HTTPS, how that token is stored, renewed,
expired and dropped, and which other account endpoints exist. Above it sits the cloud relay
authorization in [cloud-auth.md](cloud-auth.md), which consumes the token produced here. Below it
is ordinary HTTPS; the telescope firmware is not involved ([Firmware boundary](account-login/boundaries.md#firmware-boundary)). The device-side remote
control methods are in [the control catalogue](../../docs/control/methods/remote_join.md).

## Contents

| Contents | File |
|---|---|
| Conventions, endpoint selection, HTTP representation and headers | this file |
| Interactive email/password login | [account-login/login.md](account-login/login.md) |
| Account endpoint catalogue | [account-login/endpoints.md](account-login/endpoints.md) |
| Storage, startup, renewal, expiry, logout; timing; errors | [account-login/lifecycle.md](account-login/lifecycle.md) |
| Captcha and crypto, firmware boundary, open questions; validation appendix | [account-login/boundaries.md](account-login/boundaries.md) |

Requirement numbers are global across these files.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients (a replacement app or library). Sentences about what "the app" or "the server" does are
descriptions.

Labels follow `CONVENTIONS.md`:

- **READ**: seen by static analysis of the Android app 3.3.2 (Google release). It says what the
  app code does, not what the server accepts.
- **INFERRED**: a consequence or interpretation, not seen directly.
- **unresolved**: not established either way.
- No **OBSERVED** claims exist in this chapter: no live account, server or device was contacted.

Where a rule comes from a public standard (RFC 8259, RFC 9110) the RFC is cited instead of a
label. Basis for the whole chapter: static analysis of app 3.3.2 (Java/DEX), plus a literal
string scan of the firmware 9.31 imager binary ([Firmware boundary](account-login/boundaries.md#firmware-boundary)). Nothing was executed.

Throughout, `E<T>` means the response envelope `{"code": int, "msg": string, "data": T}`.

## Endpoint selection

R1. The app sends all account requests to a single fixed production origin, `https://api.seestar.com/`
([embedded-constants.md: ZWO vendor HTTP API hosts (app)](cloud-auth/embedded-constants.md#zwo-vendor-http-api-hosts-app)),
over HTTPS. The base URL ends in `/`, and endpoint paths start with `/v1/`. READ. Example:
`https://api.seestar.com/v1/user/login`.

R2. The account host is a different origin from the remote-allocation host used by
[cloud-auth.md](cloud-auth.md) ("the remote API host", `https://api-ithings.zwoastro.com`,
[embedded-constants.md: ZWO vendor HTTP API hosts (app)](cloud-auth/embedded-constants.md#zwo-vendor-http-api-hosts-app)).
READ. A client MUST NOT assume the two share cookies, base URL or error conventions (INFERRED).

R3. Host selection does not depend on the email domain, country or locale. A development test
host, `http://api-seestar-test.zwoastro.cn/`, is shipped but is reachable only through a
developer build switch that is off in this release; production is always chosen. READ. A client
SHOULD make the base URL configurable (INFERRED: regional or test deployments are not excluded by
evidence).

R4. Paths carry a literal version (`/v1/`). There is no version negotiation, and the token
response has no schema-version field. READ.

## HTTP representation

### Bodies

R5. Request bodies are JSON objects encoded in UTF-8, sent with
`Content-Type: application/json; charset=UTF-8`. They are not form fields, URL-encoded
credentials, Base64 envelopes or binary structs. READ.

R6. Serialization rules of the app's encoder: compact output; field names exactly as in the
tables below; unset nullable (reference-typed) members are **omitted**, not sent as `null`;
primitive integer members are always present, including zero. READ.

R7. Strings escape `"` and `\`, use `\b \f \n \r \t`, and encode other U+0000..U+001F as
`\u00XX`. The encoder also escapes `<`, `>`, `&`, `=`, `'` and U+2028/U+2029 as `\uXXXX`
("HTML-safe" mode). READ. These escapes change only the representation, not the value (RFC 8259).

R8. Integers are plain decimal JSON numbers; there is no fixed-offset or endian layout. No
request signature, MAC or canonical member order is applied. READ. A client MAY emit members in
any order (RFC 8259 §4); whether the server is order-sensitive is unresolved (server-side).

R9. Responses are parsed as one complete JSON document; trailing data is an error. READ.

### Transport defaults

The app's HTTP stack (OkHttp 4.12.0) adds these when the request lacks them. READ.

| Header / behaviour | Value |
|---|---|
| `Host` | from the URL |
| `Connection` | `Keep-Alive` |
| `User-Agent` | `okhttp/4.12.0` |
| `Accept-Encoding` | `gzip`, only if neither `Accept-Encoding` nor `Range` is set |
| `Content-Length` / `Transfer-Encoding` | byte length if known, else `chunked` |
| Cookies | none stored |
| TLS | platform defaults; normal hostname verification; default (empty) certificate pinner, so no pinning |
| Redirects | followed (stack default) |

R10. No evidence shows the server requires any of these stack defaults. INFERRED. A client
SHOULD still send `Content-Type` as in R5.

### Application headers

The app has three request profiles. READ.

| Header | Profile A: interactive account calls | Profile B: automatic re-login ([7.1](account-login/lifecycle.md#account-client-401-driven-credential-replay)) | Profile C: remote/cloud calls |
|---|---|---|---|
| `Authorization` | current session token, verbatim, if non-empty | not sent | stored token, verbatim, if non-empty and the request is not marked "no authentication" |
| `X-Astroimg-Authorization` | same token as `Authorization`, if non-empty | not sent | not sent |
| `x-service-platform` | caller-supplied value if non-empty, else `seestar` | not sent | `seestar` |
| `X-Lang` | `zh-CN` if the app language is Chinese, else `en` | not sent | locale tag without script; `zh`/`zh-Hans` map to `zh-CN`, `en-*` to `en` |
| `country_code` | device locale country, read per request | not sent | device locale country, read per request |
| `x-params` | JSON string, built once per process | not sent | JSON string, rebuilt per request |

R11. `x-params` is a compact JSON object with string members `channel` (`google`), `platform`
(`android`), `model` (device model), `country_code` (locale country), `os_version` (Android SDK
level as decimal text) and `app_version` (`3.3.2`). READ. In profile A the value is cached at
first use, so its `country_code` can disagree with the per-request `country_code` header after a
locale change. READ / INFERRED consequence. Whether the server checks either is unresolved (server-side).

R12. `x-service-platform` values declared in the app are `seestar`, `astronet` and `asiair`.
Some account calls (login, register, third-party register/verify) let the caller override it.
READ. A Seestar client SHOULD send `seestar`.

R13. The token is the complete header value. The app never prepends `Bearer ` or any scheme.
READ. A client MUST send the `accessToken` string exactly as received and MUST NOT parse it.
Whether the server-issued string already contains a scheme is unresolved (server-side); the
verbatim rule above applies either way.

R14. The app never decodes the token, verifies a signature or reads an embedded expiry. A class
name containing "JWT" does not establish the token format. READ.


## Relocated sections

These anchors retain navigation from generated cards; the linked sections are the primary text.

<a id="11-firmware-boundary"></a>

- [Firmware boundary](account-login/boundaries.md#firmware-boundary)

