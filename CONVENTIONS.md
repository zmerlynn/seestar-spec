# Conventions

- MUST / SHOULD / MAY follow RFC 2119 / RFC 8174.
- Confidence labels on every claim: **READ** (from firmware/app code), **OBSERVED** (seen on a device; date given), **INFERRED**, **unresolved**. **unresolved (server-side)** marks a question only the vendor's servers can answer; the client side around it is specified. Chapters may also cite **DOC** (public vendor documentation or an RFC) for background that the binaries do not themselves establish; DOC is never used in the catalog and never outranks READ.
- Each chapter ends its open questions in a section headed `Open questions` or `Not covered or unresolved`, and that section is listed in [spec/00-overview.md: Chapter open questions](spec/00-overview.md#chapter-open-questions). `tools/lint.py` enforces the listing. Cross-chapter questions get a Q-number in [spec/00-overview.md: Open-question register](spec/00-overview.md#open-question-register).
- Side-effect tier (`side_effect_tier` on each catalog entry, shown on its card): use it to decide whether a client may send a method. **A** no effect beyond request-local data. **B** observation-safe: only logging, memo or cache refreshes, lock-file creation, waiter or transport bookkeeping, and read-only relays to a peer process. **C** changes hardware (including moving the mount), persisted settings, stored files or user-visible operational state. **D** not established.
- `x-grade`: PURE GETTER or MUTATOR (established / probable).
- Reply `code`: 0 = accepted/ok; see per-method error tables.

## Catalog format

- The catalog is grouped by service, one per server or wire endpoint, listed in `catalog/index.yaml`: `control` (imager JSON, TCP 4700), `guider` (guider JSON, TCP 4400), `files` (imager image/file sockets), `serial-bridge` (guider-process ser2net control), `updater` (updater JSON, TCP 4350), `discovery`, `video`, `cloud`. A method belongs to the service whose dispatch table registers it, not the one that looks related by name. Each service has `catalog/<service>/index.yaml` listing its entries. An entry id is `<service>/<name>`; names MUST be unique across services (lint enforces this).
- One YAML file per method (`catalog/<service>/methods/<name>.yaml`) or event (`catalog/<service>/events/<Name>.yaml`). Service-specific definitions live in `catalog/<service>/schemas/`; definitions shared by several services (ids, timestamps, envelopes) live in `catalog/common/schemas/`. Files link with ordinary relative `$ref`.
- `see_also` uses a bare name for an entry in the same service and `service/name` for another service. `spec` is a list of repo-relative chapter links, `spec/<path>.md#<anchor>`, primary chapter first; lint checks that each file and heading anchor (GitHub-style slug) exists.
- A service with no documented entries keeps only an index stub (`entries: []`); create `methods/`, `events/`, `schemas/` when the first entry arrives.
- Prose chapters live in `spec/<layer>/`: `transport`, `auth`, `control`, `guider`, `updater`, `media`. A chapter longer than about 400 lines becomes an index file plus a same-named subdirectory (e.g. `transport/rdt.md` + `transport/rdt/`); requirement numbers stay continuous across the parts. Chapters are normative descriptions, not research logs: no evidence-file links, binary hashes or revision history.
- An event is filed under the service whose port it is primarily delivered on. Events also produced by the guider (channel G) and forwarded onto 4700 by the imager stay under `control` when the imager emits them too (e.g. `ScopeGoto`, `Alert`); the description names every producer.
- Entry keys: `kind`, `name`, `summary`, `description`, `grade`, `side_effect_tier`, `confidence`, `basis`, `side_effects`, `request` + `reply_success` + `reply_error` + `errors` (methods) or `payload` (events), `examples`, `see_also`, `spec`.
- Schemas are JSON Schema 2020-12. Per-property annotations are the custom keywords `x-confidence` (starts with READ, OBSERVED, INFERRED or unresolved; a short qualifier may follow) and `x-basis`. Both are required on every property. `x-default` and `x-required-when` are free-text hints for the cards where JSON Schema cannot say it.
- Every example names the schema it must satisfy in `of` (`request`, `reply_success`, `reply_error`, `payload`) and is validated by `tools/lint.py`.
- `tools/gen_cards.py` writes `docs/<service>/{methods,events}/`; `tools/lint.py` must pass before commit. Do not put network addresses (except the documentation ranges 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 and loopback), device UIDs or serials, account identifiers, coordinates of real places, home paths, key material, licence strings or long hex strings in any file. Firmware code addresses in `x-basis`/`basis` are citations, not sensitive data, and are allowed. Private keys or secrets found in binaries are never published, even in part. Fixed SDK constants needed for interoperability (embedded public keys, the legacy transform phrase, master host-name suffixes) are reproduced once, with fingerprints, in `spec/auth/cloud-auth/embedded-constants.md`; other chapters link there rather than repeat them. Licence-derived and per-account values (licences, `keyMask`, tunnel credentials, tokens) are never published. Dotted four-part version numbers trip the address check: write them as words ("4.3.8 build 0") or as a hex version word.

## Authoring notes

- Methods that return data: `allOf` the common `ReplySuccessWith.yaml` with a method-specific `properties.result` schema; do not rebuild the envelope by hand.
- A `$ref`'d params/result schema needs `x-confidence` and `x-basis` beside the `$ref` at the point of use. `anyOf`/`oneOf` wrappers under `properties` need them too.
- `spec` is optional; omit it when no chapter covers the entry yet. Prefer adding the chapter.
- After adding or removing entry files run `python3 tools/reindex.py`, then `python3 tools/lint.py`.
- Things JSON Schema cannot say (duplicate keys, error-plus-result replies, replies with no `result`/`code`) go in the description, not the schema.

## Shapes JSON Schema cannot express

Write these the same way everywhere, so tools and readers can rely on them.

- **Non-JSON replies** (binary or text transfers on `files` endpoints): `reply_success`/`reply_error` hold only `title`, `description`, `x-confidence`, `x-basis` and no `type`. The description names the framing if known, or says it is unresolved. Error rows still list the internal numeric selector.
- **Object-or-array params**: many handlers accept `{"name": v}` or a positional `[v, ...]`. Use `anyOf: [object, array]` with `prefixItems` in positional order. Positional elements inherit the label of the enclosing labelled `params`. Add `x-confidence` to an element only when it differs.
- **Scalar-or-object values**: use `anyOf` with one branch per accepted form; say in the description which form the device replies with.
- **Case-insensitive string enums**: list the canonical spellings in `enum` and add `x-case-insensitive: true`. Do not add case variants.
- **Duplicate member names** in one object (seen in some replies): give the schema for the last occurrence and describe the duplicate in `description`.
- **Dynamic-key objects** (member names are data): use `patternProperties` or `additionalProperties` with a label. Give real-looking keys only in examples.
- **Methods with no success path**: `reply_success: {description: "No success reply is established.", x-confidence: ..., x-basis: ...}` and say why.
- **Replies without `result` or `code`**: describe them in `description`; the schema allows the members the handler is shown to write.
- **Extra members on error replies** (e.g. `fullname` with code 213): add them to that method's `reply_error` via `allOf` with the common `ReplyError.yaml`.
- **Events**: `payload` is the full event object including `Event` (with `const`) and `Timestamp`, written out in full so each file stands alone (as in `ViewPlan.yaml`); `EventEnvelope.yaml` documents the common shape. Each `state`-style lifecycle field lists its values in `enum` when they are READ.

## Split chapters

Headings are unnumbered; link to a section by its heading anchor. Requirement numbers (R1..) are chapter-global across split files. The index lists parts in reading order; navigation headings such as `Contents` and `Further sections` are unnumbered. A part inherits the chapter index’s basis and conventions unless it states otherwise.

## Permalink compatibility

Covered permalinks are every file and heading anchor of `spec/**/*.md`, `docs/` cards and indexes, `README.md` and `CONVENTIONS.md`, and every `catalog/**/*.yaml` file (by file only). `tools/permalinks.py inventory` lists them.

- **Never remove a covered key that is on `v1`.** To rename, move or withdraw a section, keep an `<a id="old-slug"></a>` at the old place with a one-line notice linking the new place (relative, same ref). Point a stub at the final section, never at another stub. To move a whole file, leave the old file as a notice page that keeps its old headings or aliases.
- **Anchors.** Use ATX headings with natural text; avoid duplicate headings in one file (their `-1`, `-2` slugs shift when sections are reordered). The only other anchor form is `<a id="…"></a>`. Setext headings, other id- or name-bearing HTML, and HTML, entities, escapes or underscore emphasis inside headings are lint errors.
- **Contents.** Every covered page except this README is listed, in a list item or table row, by the nearest index above it: `<dir>/index.md`, `<dir>.md` or `<dir>-overview.md`, `spec/00-overview.md` for `spec/`, and the README for the overview, `CONVENTIONS.md` and `docs/index.md`. A new directory needs an index that its parent index lists. Card indexes are generated.
- **Retiring a catalog entry.** Keep its YAML and add `x-retired: true`, `x-retirement-reason` and `x-replaced-by: <repo path>[#anchor]`. Write the card tombstone at `tools/card-stubs/<service>/<kind>s/<name>.md`: keep the card's title heading unchanged and add `<a id="…"></a>` aliases for `summary`, `request-params`, `reply` (or `payload` for an event), `errors`, `example` and `see-also`. Then run `tools/reindex.py`, `tools/gen_cards.py` and `tools/lint.py`.
- **Pushing.** Install the hook once with `ln -s ../../tools/pre-push .git/hooks/pre-push`. Push with `git push --atomic origin HEAD:main HEAD:v1`; the hook runs lint and `tools/permalinks.py check` against the remote `v1`, and refuses a lone `main` push, a non-fast-forward `v1`, or any removed key. Pull requests merged on GitHub reach `v1` through CI (`.github/workflows/lint.yml`), which runs the same checks on `main` and then fast-forwards `v1`. `tools/MAJOR` names the current major; when it changes, the old branch is frozen.
