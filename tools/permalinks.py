#!/usr/bin/env python3
"""Permalink inventory and compatibility check (see CONVENTIONS.md, Permalink compatibility).

  permalinks.py inventory [--ref REF]          list covered keys (path or path#fragment)
  permalinks.py lint [--ref REF]               anchor, link and stub problems only
  permalinks.py check --base REF --ref REF     fail if any key at base is missing at ref
  permalinks.py check --initial --ref REF      first commit of a major: problems only

Without --ref the working tree is read. Refs are read with git plumbing; nothing is checked out
and no code from either ref is run.
"""
import argparse
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anchors  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARD = re.compile(r"^docs/(index|[^/]+/index|[^/]+/(methods|events)/[^/]+)\.md$")
TOC_LINE = re.compile(r"^\s*([-*+]|\d+\.|\|)\s")


def covered(path):
    if path in ("README.md", "CONVENTIONS.md") or CARD.match(path):
        return True
    return (path.startswith("spec/") and path.endswith(".md")) or \
        (path.startswith("catalog/") and path.endswith(".yaml"))


def is_markdown(path):
    return path.endswith(".md")


def git(*args, data=None):
    return subprocess.run(("git", "-C", ROOT) + args, input=data, capture_output=True, check=True).stdout


class Tree:
    """Files of one commit, or of the working tree when ref is None."""

    def __init__(self, ref=None):
        self.ref = ref
        if ref is None:
            self.commit = None
            self.paths = set()
            for d, dirs, files in os.walk(ROOT):
                dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
                for f in files:
                    self.paths.add(os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/"))
        else:
            self.commit = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
            self.paths = set()
            for rec in git("ls-tree", "-r", "-z", self.commit).split(b"\0"):
                if not rec:
                    continue
                meta, path = rec.decode("utf-8").split("\t", 1)
                mode, kind = meta.split()[:2]
                if covered(path) and (kind != "blob" or mode not in ("100644", "100755")):
                    raise SystemExit("%s: covered path %s is not a regular file" % (ref, path))
                self.paths.add(path)
        self._docs, self._blobs = {}, None
        self.dirs = {posixpath.dirname(p) for p in self.paths}
        for d in list(self.dirs):
            while d:
                d = posixpath.dirname(d)
                self.dirs.add(d)

    def read(self, path):
        if self.commit is None:
            with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
                return fh.read()
        if self._blobs is None:
            self._load_blobs()
        return self._blobs[path]

    def _load_blobs(self):
        """Read every covered Markdown blob of the commit in one git cat-file call."""
        want = sorted(p for p in self.paths if covered(p) and is_markdown(p))
        raw = git("cat-file", "--batch", data="".join("%s:%s\n" % (self.commit, p) for p in want).encode())
        self._blobs, pos = {}, 0
        for p in want:
            nl = raw.index(b"\n", pos)
            size = int(raw[pos:nl].split()[2])
            self._blobs[p] = raw[nl + 1:nl + 1 + size].decode("utf-8")
            pos = nl + 1 + size + 1

    def doc(self, path):
        if path not in self._docs:
            self._docs[path] = anchors.parse(self.read(path))
        return self._docs[path]

    def keys(self):
        out = set()
        for p in self.paths:
            if not covered(p):
                continue
            out.add(p)
            if is_markdown(p):
                out.update("%s#%s" % (p, a) for a in self.doc(p).anchors)
        return out


def resolve_link(src, target):
    """(path, fragment) a local link points to, or None for external links."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("//"):
        return None
    path, _, frag = target.partition("#")
    path = unquote(path)
    dest = posixpath.normpath(posixpath.join(posixpath.dirname(src), path)) if path else src
    return dest, unquote(frag)


def problems(tree):
    """Anchor, link and stub problems in covered Markdown, as sorted 'path:line: message' strings."""
    out = []
    md = sorted(p for p in tree.paths if covered(p) and is_markdown(p))
    for p in md:
        d = tree.doc(p)
        out += ["%s:%d: %s" % (p, n, m) for n, m in d.errors]
        for n, target, alias in d.links:
            r = resolve_link(p, target)
            if r is None:
                continue
            dest, frag = r
            if dest.startswith("../") or (dest not in tree.paths and dest not in tree.dirs):
                out.append("%s:%d: broken link %s" % (p, n, target))
                continue
            if frag and is_markdown(dest):
                kind = tree.doc(dest).anchors.get(frag) if dest in tree.paths else None
                if kind is None:
                    out.append("%s:%d: broken anchor %s" % (p, n, target))
                elif alias and kind[0] == "alias":
                    out.append("%s:%d: stub #%s points at another stub %s (link the final section)" % (p, n, alias, target))
            elif frag and dest.endswith(".yaml"):
                out.append("%s:%d: fragment on a YAML link %s" % (p, n, target))
    return sorted(out + toc_problems(tree))


def index_of(tree, d):
    """The index page of directory d: d/index.md, d.md or d-overview.md; the overview for spec/."""
    if d == "spec":
        return "spec/00-overview.md"
    if d == "":
        return "README.md"
    for c in (d + "/index.md", d + ".md", d + "-overview.md"):
        if c in tree.paths:
            return c
    return None


def toc_parent(tree, p):
    """The nearest index above page p, which must list it."""
    if p in ("spec/00-overview.md", "CONVENTIONS.md", "docs/index.md"):
        return "README.md"
    d = posixpath.dirname(p)
    if index_of(tree, d) == p:          # p indexes its own directory: look one level up
        d = posixpath.dirname(d)
    while True:
        i = index_of(tree, d)
        if i and i != p:
            return i
        d = posixpath.dirname(d)


def toc_problems(tree):
    """Every covered page must be listed (in a list item or table row) by its nearest index."""
    out, toc = [], {}
    for p in sorted(x for x in tree.paths if covered(x) and is_markdown(x) and x != "README.md"):
        q = toc_parent(tree, p)
        if q not in toc:
            item, in_item = set(), False   # line numbers inside list items or table rows
            for n, line in enumerate(tree.read(q).split("\n"), 1):
                in_item = bool(TOC_LINE.match(line)) or (in_item and line[:1] in (" ", "\t") and line.strip() != "")
                if in_item:
                    item.add(n)
            toc[q] = set()
            for n, target, _ in tree.doc(q).links:
                r = resolve_link(q, target)
                if r and n in item:
                    toc[q].add(r[0])
        if p not in toc[q]:
            out.append("%s: not listed in the contents of its index %s" % (p, q))
    return out


def report(label, items, limit=None):
    if items:
        print("%s (%d):" % (label, len(items)))
        for x in (items if limit is None else items[:limit]):
            print("  " + x)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("inventory", "lint", "check"))
    ap.add_argument("--ref")
    ap.add_argument("--base")
    ap.add_argument("--initial", action="store_true")
    a = ap.parse_args(argv)
    tree = Tree(a.ref)
    if a.mode == "inventory":
        for k in sorted(tree.keys()):
            print(k)
        return 0
    bad = problems(tree)
    report("problems", bad)
    if a.mode == "lint":
        print("permalinks lint: %s (%d problems)" % ("FAILED" if bad else "ok", len(bad)))
        return 1 if bad else 0
    if a.initial == bool(a.base):
        ap.error("check needs exactly one of --base or --initial")
    if a.ref is None:
        ap.error("check reads a commit; pass --ref")
    removed, added = [], []
    if a.base:
        base = Tree(a.base)
        if subprocess.run(("git", "-C", ROOT, "merge-base", "--is-ancestor", base.commit, tree.commit)).returncode:
            print("FAIL %s is not an ancestor of %s (the branch only fast-forwards)" % (a.base, a.ref))
            return 1
        old, new = base.keys(), tree.keys()
        removed, added = sorted(old - new), sorted(new - old)
        report("removed permalinks", removed)
        report("added permalinks", added, 50)
    ok = not bad and not removed
    print("permalinks: %s (%d keys, %d removed, %d added, %d problems)" % (
        "ok" if ok else "FAILED", len(tree.keys()), len(removed), len(added), len(bad)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
