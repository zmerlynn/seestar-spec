"""Shared YAML loading and $ref resolution for the spec tools."""
import copy
import os
import re
import yaml

import anchors

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_cache = {}


def load(path):
    path = os.path.abspath(path)
    if path not in _cache:
        with open(path, encoding="utf-8") as fh:
            _cache[path] = yaml.safe_load(fh)
    return _cache[path]


def split_ref(ref, base):
    file_part, _, frag = ref.partition("#")
    target = os.path.abspath(os.path.join(os.path.dirname(base), file_part)) if file_part else base
    return target, frag


def pointer(doc, frag):
    node = doc
    for part in [p for p in frag.split("/") if p]:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def resolve(node, base, stack=()):
    """Return a deep copy of node with every $ref replaced by its target."""
    if isinstance(node, list):
        return [resolve(n, base, stack) for n in node]
    if not isinstance(node, dict):
        return copy.deepcopy(node)
    if "$ref" in node:
        target_file, frag = split_ref(node["$ref"], base)
        key = (target_file, frag)
        if key in stack:
            return {"$circular": node["$ref"]}
        target = pointer(load(target_file), frag)
        out = resolve(target, target_file, stack + (key,))
        for k, v in node.items():
            if k != "$ref":
                out[k] = resolve(v, base, stack)
        return out
    return {k: resolve(v, base, stack) for k, v in node.items()}


def iter_refs(node, base):
    """Yield (ref, base) for every $ref in an unresolved document tree."""
    if isinstance(node, dict):
        if "$ref" in node:
            yield node["$ref"], base
        for v in node.values():
            yield from iter_refs(v, base)
    elif isinstance(node, list):
        for v in node:
            yield from iter_refs(v, base)


CATALOG = os.path.join(ROOT, "catalog")


def load_index():
    """Top-level index: format, services list."""
    return load(os.path.join(CATALOG, "index.yaml"))


def service_index_path(service):
    return os.path.join(CATALOG, service, "index.yaml")


def load_service_index(service):
    return load(service_index_path(service))


def services():
    return [s["name"] for s in load_index().get("services", [])]


def all_entries():
    """Yield (service, entry-record) for every entry of every service; id is service/name."""
    for svc in services():
        for en in load_service_index(svc).get("entries") or []:
            yield svc, en


def entry_path(service, rel):
    return os.path.join(CATALOG, service, rel)


def load_entry(service, rel):
    """Load a catalog entry with all $refs resolved."""
    path = entry_path(service, rel)
    return resolve(load(path), path)


def spec_links(entry):
    """An entry's `spec:` value as a list of 'path[#anchor]' strings, primary first."""
    v = entry.get("spec")
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def headings(path):
    """(title, {anchor: heading text, or "" for an explicit alias}) for a markdown file, relative to ROOT."""
    if path not in _HEAD:
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            d = anchors.parse(fh.read())
        _HEAD[path] = (d.title, {a: text for a, (_, _, text) in d.anchors.items()})
    return _HEAD[path]


_HEAD = {}


def is_retired(doc):
    return isinstance(doc, dict) and doc.get("x-retired") is True


def retired_entries():
    """(service, kind, name, file) for every entry file marked x-retired: true."""
    for svc in services():
        for sub, kind in (("methods", "method"), ("events", "event")):
            d = os.path.join(CATALOG, svc, sub)
            for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                if fn.endswith(".yaml") and is_retired(load(os.path.join(d, fn))):
                    yield svc, kind, load(os.path.join(d, fn))["name"], "%s/%s" % (sub, fn)
