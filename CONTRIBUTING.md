# Contributing

Corrections and new evidence are welcome. The most useful report names the claim, says what you
saw instead, and says where your evidence came from.

## Reporting an error

Open an issue with:

- a link to the section on the `v1` branch (e.g. `blob/v1/spec/control/stacking.md#…`);
- the claim and what is wrong with it;
- the firmware and app versions, and the device model, you checked against;
- your evidence and its kind: READ (you read it in the firmware or app code), OBSERVED (you saw it
  on a device; give the date) or INFERRED (see [CONVENTIONS](CONVENTIONS.md)).

Reports on firmware or app versions that this specification does not cover yet are welcome; say so,
and the result is added as a version-tagged extension.

## Clean-room rule

This specification is written only from static analysis of firmware and app binaries and from
observation of real devices. Contributions must come from the same kind of sources, your own work:

- Do not submit anything taken or derived from other implementations of these protocols: their
  code, documentation, wikis, issue threads or write-ups. This holds even if they are open source,
  and also for text you had an AI tool produce from them.
- Do not submit vendor-confidential material.
- State your sources. If you are not sure whether a source is allowed, ask in the issue before you
  write anything.

## What never goes in

Do not put any of these in an issue, a pull request or an attachment:

- passwords, tokens, keys, licence or session values, account names or e-mail addresses;
- device identifiers (serial numbers, UIDs, MAC addresses) or real IP addresses (use the RFC 5737
  documentation ranges);
- firmware images, app packages or large excerpts of them;
- packet captures or logs that have not been reduced to the fields that matter.

If you find any of these already published here, do not open a public issue: report it privately
through GitHub's private vulnerability reporting (the Security tab). Security problems in the device,
the app or the vendor's services belong with the vendor, not here.

## Pull requests

Follow [CONVENTIONS](CONVENTIONS.md). In short:

- Every claim carries a confidence label, and behaviour that differs by version is tagged with the
  version.
- Keep binary addresses and internal function names out of prose; they go in the catalog's basis
  fields.
- The catalog is the source of truth for methods and events. Never edit `docs/` by hand: run
  `tools/reindex.py` and `tools/gen_cards.py`, then `tools/lint.py` (Python 3 with PyYAML and jsonschema).
- Never remove a section heading or file that is on `v1`. To rename, move or withdraw one, leave a
  notice at the old place ([Permalink compatibility](CONVENTIONS.md#permalink-compatibility)).
  `tools/permalinks.py check --base origin/v1 --ref HEAD` shows what a change would remove.

CI runs the generators, the lint and the permalink check on every pull request. Accepted pull
requests are squash-merged into `main`; when the checks pass there, CI fast-forwards `v1` to the
same commit.

## License

By contributing you agree that your contribution is dedicated to the public domain under CC0 1.0,
like the rest of this repository ([LICENSE](LICENSE)).
