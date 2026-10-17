#!/usr/bin/env python3
"""Rewrite the `entries:` block of every catalog/<service>/index.yaml from the entry files on disk."""
import os, re, sys, yaml
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "catalog")

def entries(svc_dir):
    out = []
    for sub, kind in (("methods", "method"), ("events", "event")):
        d = os.path.join(svc_dir, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".yaml"):
                doc = yaml.safe_load(open(os.path.join(d, fn)))
                if doc.get("x-retired") is True:
                    continue  # retired entries keep their file but leave the index
                out.append((kind, doc["name"], "%s/%s" % (sub, fn)))
    return out

for svc in sorted(os.listdir(ROOT)):
    ipath = os.path.join(ROOT, svc, "index.yaml")
    if not os.path.isfile(ipath):
        continue
    text = open(ipath).read()
    ents = entries(os.path.join(ROOT, svc))
    block = "entries:" + (" []\n" if not ents else "\n" + "".join(
        "  - {kind: %s, name: %s, file: %s}\n" % e for e in ents))
    new = re.sub(r"^entries:.*?(?=^\S|\Z)", block, text, count=1, flags=re.S | re.M)
    if new != text:
        open(ipath, "w").write(new)
        print("reindexed", svc, len(ents))
