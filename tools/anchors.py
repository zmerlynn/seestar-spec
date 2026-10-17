"""Markdown anchor and link parsing shared by lint, card generation and the permalink checker.

Supported, deliberately small Markdown subset (anything else that could carry an anchor is an error):
ATX headings, backtick/tilde fences, HTML comments, code spans, inline and reference links, and the explicit
alias form `<a id="..."></a>`. Setext headings and other id-bearing HTML are rejected.
"""
import html
import re

HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
ALIAS = re.compile(r"""<a\s+id\s*=\s*(?:"([^"\s]+)"|'([^'\s]+)')\s*></a>""")
ANY_ID = re.compile(r"""<[A-Za-z][^>]*\s(?:id|name)\s*=""")
LINK = re.compile(r"!?\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REFDEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?")
CODE = re.compile(r"(`+)(.+?)\1")
EMPH_UNDERSCORE = re.compile(r"(?<![\w])_[^_\s][^_]*_(?![\w])|__")


def _strip_code(line):
    """Line with code-span contents blanked out, so markup inside them is ignored."""
    return CODE.sub(lambda m: " " * len(m.group(0)), line)


def heading_text(raw):
    """Rendered text of an ATX heading's inline content, or raise ValueError if unsupported."""
    plain = _strip_code(raw)
    if "<" in plain or "&" in plain or "\\" in plain:
        raise ValueError("HTML, entity or escape in heading")
    if EMPH_UNDERSCORE.search(plain):
        raise ValueError("underscore emphasis in heading")
    out, pos = [], 0
    for m in CODE.finditer(raw):
        out.append(LINK.sub(lambda l: l.group(1), raw[pos:m.start()]))
        out.append(m.group(2))
        pos = m.end()
    out.append(LINK.sub(lambda l: l.group(1), raw[pos:]))
    return html.unescape("".join(out))


def slug(text):
    """GitHub-style base slug of rendered heading text."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


class Doc:
    """Parsed anchors and links of one Markdown document."""

    def __init__(self, text):
        self.title = None
        self.anchors = {}   # id -> ("heading"|"alias", line number, heading text or "")
        self.links = []     # (line number, target, alias id whose block holds the link, or None)
        self.errors = []    # (line number, message)
        self._occ = {}
        self._parse(text.split("\n"))

    def _add(self, aid, kind, n, text):
        if aid in self.anchors:
            self.errors.append((n, "duplicate anchor #%s (first at line %d)" % (aid, self.anchors[aid][1])))
            return
        self.anchors[aid] = (kind, n, text)

    def _allocate(self, base):
        # github-slugger: a repeated slug gets the next unused -N suffix of its base.
        result = base
        while result in self._occ:
            self._occ[base] += 1
            result = "%s-%d" % (base, self._occ[base])
        self._occ[result] = 0
        return result

    def _parse(self, lines):
        fence, comment, prev_text, block, blank = None, False, False, None, False
        for n, line in enumerate(lines, 1):
            if fence:
                m = FENCE.match(line)
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip(fence[0] + " \t"):
                    fence = None
                continue
            if comment:
                if "-->" in line:
                    comment = False
                continue
            m = FENCE.match(line)
            if m:
                fence, prev_text = m.group(1), False
                continue
            if line.lstrip().startswith("<!--") and "-->" not in line:
                comment = True
                continue
            body = re.sub(r"<!--.*?-->", "", line)
            h = HEADING.match(body)
            if h:
                block = None
                try:
                    text = heading_text(h.group(2) or "")
                except ValueError as exc:
                    self.errors.append((n, "unsupported heading markup: %s" % exc))
                    text = h.group(2) or ""
                self.title = self.title or text
                aid = self._allocate(slug(text))
                self._add(aid, "heading", n, text)
                prev_text = False
                continue
            if block and blank and body.strip() and not re.match(r"^(\s+|[-*] |<a )", body):
                block = None
            blank = not body.strip()
            if SETEXT.match(body) and prev_text:
                self.errors.append((n, "Setext heading underline (use an ATX heading)"))
            plain = _strip_code(body)
            for a in ALIAS.finditer(plain):
                aid = a.group(1) or a.group(2)
                self._add(aid, "alias", n, "")
                block = aid
            if ANY_ID.search(ALIAS.sub("", plain)):
                self.errors.append((n, "unsupported HTML anchor (only <a id=\"...\"></a>)"))
            r = REFDEF.match(body)
            if r:
                self.links.append((n, r.group(1), block))
                continue
            for l in LINK.finditer(plain):
                target = body[l.start(2):l.end(2)]
                self.links.append((n, target, block))
            prev_text = bool(body.strip()) and not body.lstrip().startswith(("|", "<a "))
        if fence:
            self.errors.append((len(lines), "unclosed code fence"))


def parse(text):
    return Doc(text)
