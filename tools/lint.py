#!/usr/bin/env python3
"""Lint the spec: YAML parses, $refs resolve, fields carry x-confidence, no sensitive values,
links and anchors resolve, every page is in a contents list, and docs/ matches the catalog."""
import glob
import ipaddress
import os
import re
import sys

import anchors
import gen_cards
import permalinks
import specload as S

LABELS = ("READ", "OBSERVED", "INFERRED", "unresolved")
TIERS = ("A", "B", "C", "D")
errors = []


def err(where, msg):
    errors.append("%s: %s" % (os.path.relpath(where, S.ROOT) if os.path.isabs(where) else where, msg))


def catalog_files():
    return sorted(glob.glob(os.path.join(S.CATALOG, "**", "*.yaml"), recursive=True))


def check_parse_and_refs():
    for path in catalog_files():
        try:
            doc = S.load(path)
        except Exception as exc:  # noqa: BLE001
            err(path, "YAML does not parse: %s" % exc)
            continue
        for ref, base in S.iter_refs(doc, path):
            target, frag = S.split_ref(ref, base)
            if not os.path.exists(target):
                err(path, "$ref %s: file not found" % ref)
                continue
            try:
                S.pointer(S.load(target), frag)
            except (KeyError, IndexError, ValueError, TypeError):
                err(path, "$ref %s: pointer does not resolve" % ref)


def has_label(value):
    return isinstance(value, str) and any(value.startswith(label) for label in LABELS)


def walk_schema(node, where, trail, inherited=False):
    if isinstance(node, dict):
        inherited = inherited or has_label(node.get("x-confidence"))
        props = node.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                if not isinstance(sub, dict):
                    err(where, "%s.%s: property schema is not a mapping" % (trail, name))
                    continue
                if not has_label(sub.get("x-confidence")):
                    err(where, "%s.%s: missing or invalid x-confidence" % (trail, name))
                if not sub.get("x-basis"):
                    err(where, "%s.%s: missing x-basis" % (trail, name))
        # Positional elements and dynamic-key members are claims too; they inherit from a labelled parent.
        labelled = []
        if not inherited:
            labelled = [("%s.prefixItems[%d]" % (trail, i), sub) for i, sub in enumerate(node.get("prefixItems") or [])]
            labelled += [("%s.patternProperties[%s]" % (trail, k), sub)
                         for k, sub in (node.get("patternProperties") or {}).items()]
            if isinstance(node.get("additionalProperties"), dict):
                labelled.append(("%s.additionalProperties" % trail, node["additionalProperties"]))
        for label, sub in labelled:
            if isinstance(sub, dict) and not has_label(sub.get("x-confidence")):
                err(where, "%s: missing or invalid x-confidence" % label)
            if isinstance(sub, dict) and not sub.get("x-basis"):
                err(where, "%s: missing x-basis" % label)
        for key, val in node.items():
            walk_schema(val, where, "%s.%s" % (trail, key) if key != "properties" else trail, inherited)
    elif isinstance(node, list):
        for i, val in enumerate(node):
            walk_schema(val, where, "%s[%d]" % (trail, i), inherited)


COMMON = ("kind", "name", "summary", "grade", "side_effect_tier", "confidence", "basis",
          "side_effects", "examples", "see_also")
SCHEMA_KEYS = {"method": ("request", "reply_success", "reply_error"), "event": ("payload",)}


def check_entries():
    import jsonschema  # required: example validation is a mandatory check

    top_path = os.path.join(S.CATALOG, "index.yaml")
    top = S.load(top_path)
    svc_names = [x["name"] for x in top.get("services", [])]
    if len(set(svc_names)) != len(svc_names):
        err(top_path, "duplicate service name")
    ids = {}
    records = []
    for svc in svc_names:
        ipath = S.service_index_path(svc)
        if not os.path.exists(ipath):
            err(top_path, "service %s: index.yaml missing" % svc)
            continue
        idx = S.load(ipath)
        if idx.get("service") != svc:
            err(ipath, "service key must be %s" % svc)
        for en in idx.get("entries") or []:
            nm = en.get("name")
            if nm in ids:
                err(ipath, "name %s clashes with %s" % (nm, ids[nm]))
            ids[nm] = "%s/%s" % (svc, nm)
            records.append((svc, en))
    listed = set()
    for svc, en in records:
        ipath = S.service_index_path(svc)
        listed.add((svc, os.path.normpath(en["file"])))
        path = S.entry_path(svc, en["file"])
        if not os.path.exists(path):
            err(ipath, "entry file %s missing" % en["file"])
            continue
        e = S.load_entry(svc, en["file"])
        where = "%s/%s" % (svc, en["file"])
        if (e.get("kind"), e.get("name")) != (en["kind"], en["name"]):
            err(where, "kind/name disagree with index")
        for k in COMMON + SCHEMA_KEYS.get(e.get("kind"), ()):
            if k not in e:
                err(where, "missing key %s" % k)
        if e.get("kind") == "method" and "errors" not in e:
            err(where, "method needs an errors table")
        if not has_label(e.get("confidence")):
            err(where, "confidence must start with one of %s" % ", ".join(LABELS))
        if e.get("side_effect_tier") not in TIERS:
            err(where, "side_effect_tier must be one of A-D")
        for row in e.get("errors", []):
            if not all(k in row for k in ("code", "trigger", "label")):
                err(where, "errors row needs code, trigger, label")
        for name in (e.get("see_also") or []):
            full = name if "/" in name else svc + "/" + name
            if ids.get(full.split("/")[-1]) != full:
                err(where, "see_also %s is not an entry (use service/name across services)" % name)
        for link in S.spec_links(e):
            path, _, anchor = link.partition("#")
            if not os.path.exists(os.path.join(S.ROOT, path)):
                err(where, "spec chapter %s not found" % path)
            elif anchor and anchor not in S.headings(path)[1]:
                err(where, "spec anchor %s not found" % link)
        schemas = {}
        for k in SCHEMA_KEYS.get(e.get("kind"), ()):
            if k not in e:
                continue
            schemas[k] = e[k]
            walk_schema(e[k], where, k)
            try:
                jsonschema.Draft202012Validator.check_schema(e[k])
            except jsonschema.SchemaError as exc:
                err(where, "%s is not a valid 2020-12 schema: %s" % (k, exc.message))
        for ex in e.get("examples", []):
            target = schemas.get(ex.get("of"))
            if target is None:
                err(where, "example %s: unknown 'of' %s" % (ex.get("name"), ex.get("of")))
                continue
            try:
                jsonschema.Draft202012Validator(target).validate(ex["payload"])
            except jsonschema.ValidationError as exc:
                err(where, "example %s invalid against %s: %s" % (ex.get("name"), ex["of"], exc.message))
    for svc in svc_names:
        for sub in ("methods", "events"):
            for path in glob.glob(os.path.join(S.CATALOG, svc, sub, "*.yaml")):
                rel = os.path.normpath(os.path.relpath(path, os.path.join(S.CATALOG, svc)))
                retired = S.is_retired(S.load(path))
                if retired and (svc, rel) in listed:
                    err(path, "retired entry is still listed in its service index (run tools/reindex.py)")
                elif retired:
                    check_retired(path, S.load(path))
                elif (svc, rel) not in listed:
                    err(path, "entry file not listed in its service index")
    for d in sorted(os.listdir(S.CATALOG)):
        if os.path.isdir(os.path.join(S.CATALOG, d)) and d not in svc_names + ["common"]:
            err(os.path.join(S.CATALOG, d), "directory is neither a listed service nor common")
    for path in sorted(glob.glob(os.path.join(S.CATALOG, "*", "schemas", "*.yaml"))):
        walk_schema(S.resolve(S.load(path), path), os.path.relpath(path, S.CATALOG), "schema", True)  # root is labelled at its point of use
    for svc in svc_names:
        idx = S.load(S.service_index_path(svc))
        for key, ref in (idx.get("envelope") or {}).items():
            resolved = S.resolve(ref, S.service_index_path(svc))
            walk_schema(resolved, "%s envelope.%s" % (svc, key), key)


def check_retired(path, doc):
    """A retired entry keeps valid YAML and names why and where its content went."""
    if not str(doc.get("x-retirement-reason") or "").strip():
        err(path, "retired entry needs x-retirement-reason")
    dest = doc.get("x-replaced-by")
    if not dest:
        err(path, "retired entry needs x-replaced-by (repo-relative path[#anchor])")
        return
    target, _, frag = str(dest).partition("#")
    full = os.path.join(S.ROOT, target)
    if not os.path.exists(full):
        err(path, "x-replaced-by %s: file not found" % dest)
    elif frag and target.endswith(".md") and frag not in S.headings(target)[1]:
        err(path, "x-replaced-by %s: anchor not found" % dest)


def check_pages():
    for p in permalinks.problems(permalinks.Tree()):
        err(p.split(":", 1)[0], p.split(": ", 1)[1] if ": " in p else p)
    for p in gen_cards.check():
        err(p.split(":", 1)[0], p.split(": ", 1)[1])


# ---- sensitive values ------------------------------------------------------
# Patterns are assembled from pieces so this file does not trip its own scan.
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
IPV4 = re.compile(r"(?<![\w.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\w.])")
HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
KEYBLOCK = re.compile("BEG" + r"IN[ A-Z]*" + "KE" + "Y")
COORD = re.compile(r"(?<![\d.])[-+]?\d{1,3}\.\d{3,}\s*[,;]\s*[-+]?\d{1,3}\.\d{3,}(?![\d])")
LATLON = re.compile(r"""["']?\b(?:lat|lon|lng|latitude|longitude)["']?\s*[:=]\s*[-+]?\d""", re.I)
HOMEPATH = re.compile("/ho" + "me/[A-Za-z0-9_.-]+|/Us" + "ers/[A-Za-z0-9_.-]+")
PRIVKEY = re.compile("PRIV" + "ATE " + "KE" + "Y")
# The one file that publishes fixed SDK constants (public keys, phrase, fingerprints).
# It is exempt from the hex and public-key-block checks only; private keys fail everywhere.
CONSTANTS_FILE = os.path.join("spec", "auth", "cloud-auth", "embedded-constants.md")
# A GitHub-owned action pinned to a commit in a workflow: the only other hex the repository allows.
ACTION_PIN = re.compile(r"^\s*(- )?uses: actions/[\w.-]+@[0-9a-f]{40} # v[0-9.]+$")


def ip_ok(m):
    octets = [int(g) for g in m.groups()]
    if any(o > 255 for o in octets):
        return True  # not an address (e.g. a version string)
    ip = ipaddress.ip_address(".".join(map(str, octets)))
    return str(ip) in ("0.0.0.0", "127.0.0.1") or any(ip in n for n in DOC_NETS)


def check_sensitive():
    me = os.path.abspath(__file__)
    for dirpath, dirnames, filenames in os.walk(S.ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if os.path.abspath(path) == me or fn.endswith(".pyc"):
                continue
            try:
                lines = open(path, encoding="utf-8").read().splitlines()
            except UnicodeDecodeError:
                err(path, "binary file in repository")
                continue
            rel = os.path.relpath(path, S.ROOT).replace(os.sep, "/")
            for n, line in enumerate(lines, 1):
                where = "%s:%d" % (rel, n)
                for m in IPV4.finditer(line):
                    if not ip_ok(m):
                        err(where, "IPv4 address")
                constants = os.path.relpath(path, S.ROOT) == CONSTANTS_FILE
                pin = rel.startswith(".github/workflows/") and ACTION_PIN.match(line)
                if HEX.search(line) and not constants and not pin:
                    err(where, "long hex blob")
                if PRIVKEY.search(line):
                    err(where, "private key marker")
                elif KEYBLOCK.search(line) and not constants:
                    err(where, "key block marker")
                if COORD.search(line) or LATLON.search(line):
                    err(where, "coordinates-looking value")
                if HOMEPATH.search(line):
                    err(where, "absolute home path")


OPEN_TITLES = ("Open questions", "Not covered or unresolved")


def open_question_sections():
    """(path relative to spec/, anchor) for every chapter open-question heading."""
    spec = os.path.join(S.ROOT, "spec")
    out = []
    for path in sorted(glob.glob(os.path.join(spec, "**", "*.md"), recursive=True)):
        rel = os.path.relpath(path, spec)
        if rel == "00-overview.md":
            continue
        doc = anchors.parse(open(path, encoding="utf-8").read())
        for anchor, (kind, _, text) in sorted(doc.anchors.items(), key=lambda kv: kv[1][1]):
            if kind == "heading" and text in OPEN_TITLES:
                out.append((rel, anchor))
    return out


def check_open_index():
    overview = os.path.join(S.ROOT, "spec", "00-overview.md")
    text = open(overview, encoding="utf-8").read()
    for rel, anchor in open_question_sections():
        if "(%s#%s)" % (rel, anchor) not in text:
            err(overview, "open-question section not indexed in the open-question register: %s#%s" % (rel, anchor))


def main():
    check_parse_and_refs()
    if not errors:
        check_entries()
    check_sensitive()
    check_open_index()
    check_pages()
    for e in errors:
        print("FAIL", e)
    print("lint: %s (%d problem%s)" % ("FAILED" if errors else "ok", len(errors), "" if len(errors) == 1 else "s"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
