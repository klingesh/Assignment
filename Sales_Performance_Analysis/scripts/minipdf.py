#!/usr/bin/env python3
"""
minipdf - a tiny dependency-free PDF writer
===========================================

Written because this environment has no network access, so reportlab / fpdf /
pandoc / wkhtmltopdf are all unavailable. Uses only the Python standard library.

Supports what a report actually needs:
  * A4 pages with automatic page breaks and footers
  * Headings (3 levels), body text, bullet and numbered lists
  * Inline **bold** and `monospace` runs inside body text
  * Tables with header fill, zebra striping, cell wrapping and page-spanning
    (the header row is redrawn on continuation pages)
  * Syntax-neutral code blocks with a tinted background
  * Callout / quote boxes with a coloured left bar
  * Horizontal rules and a cover page

Text is measured with the real Adobe base-14 AFM advance widths for Helvetica
and Helvetica-Bold, so wrapping is accurate rather than estimated. Fonts use
WinAnsiEncoding.
"""

import re

# --------------------------------------------------------------------------
# Font metrics (units per 1000 em) - Adobe base-14 AFM advance widths
# --------------------------------------------------------------------------

_HELV = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667,
    "'": 191, '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333,
    '.': 278, '/': 278, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584,
    '?': 556, '@': 1015, '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556,
    '`': 333, '{': 334, '|': 260, '}': 334, '~': 584,
    'A': 667, 'B': 667, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
    'H': 722, 'I': 278, 'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722,
    'O': 778, 'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722,
    'V': 667, 'W': 944, 'X': 667, 'Y': 667, 'Z': 611,
    'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556, 'f': 278, 'g': 556,
    'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222, 'm': 833, 'n': 556,
    'o': 556, 'p': 556, 'q': 556, 'r': 333, 's': 500, 't': 278, 'u': 556,
    'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 500,
}
_HELV.update({d: 556 for d in '0123456789'})

_HELVB = {
    ' ': 278, '!': 333, '"': 474, '#': 556, '$': 556, '%': 889, '&': 722,
    "'": 238, '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333,
    '.': 278, '/': 278, ':': 333, ';': 333, '<': 584, '=': 584, '>': 584,
    '?': 611, '@': 975, '[': 333, '\\': 278, ']': 333, '^': 584, '_': 556,
    '`': 333, '{': 389, '|': 280, '}': 389, '~': 584,
    'A': 722, 'B': 722, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
    'H': 722, 'I': 278, 'J': 556, 'K': 722, 'L': 611, 'M': 833, 'N': 722,
    'O': 778, 'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722,
    'V': 667, 'W': 944, 'X': 667, 'Y': 667, 'Z': 611,
    'a': 556, 'b': 611, 'c': 556, 'd': 611, 'e': 556, 'f': 333, 'g': 611,
    'h': 611, 'i': 278, 'j': 278, 'k': 556, 'l': 278, 'm': 889, 'n': 611,
    'o': 611, 'p': 611, 'q': 611, 'r': 389, 's': 556, 't': 333, 'u': 611,
    'v': 556, 'w': 778, 'x': 556, 'y': 556, 'z': 500,
}
_HELVB.update({d: 556 for d in '0123456789'})

# style key -> (pdf font resource name, width table)
FONTS = {
    'r': ('F1', _HELV),     # Helvetica
    'b': ('F2', _HELVB),    # Helvetica-Bold
    'i': ('F5', _HELV),     # Helvetica-Oblique (same metrics as regular)
    'c': ('F3', None),      # Courier      - fixed 600
    'cb': ('F4', None),     # Courier-Bold - fixed 600
}

_BASE_FONTS = [
    ('F1', 'Helvetica'),
    ('F2', 'Helvetica-Bold'),
    ('F3', 'Courier'),
    ('F4', 'Courier-Bold'),
    ('F5', 'Helvetica-Oblique'),
]

# Characters outside WinAnsiEncoding, mapped to safe equivalents.
_TRANSLATE = [
    ('\u20b9', 'Rs '), ('\u2192', '->'), ('\u2190', '<-'), ('\u2014', '-'),
    ('\u2013', '-'), ('\u2018', "'"), ('\u2019', "'"), ('\u201c', '"'),
    ('\u201d', '"'), ('\u2026', '...'), ('\u2265', '>='), ('\u2264', '<='),
    ('\u2248', '~'), ('\u00d7', 'x'), ('\u2713', 'Y'), ('\u2717', 'N'),
    ('\u25b2', '^'), ('\u25bc', 'v'), ('\u2022', '\u2022'),
]

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

INK = (0.13, 0.14, 0.16)
MUTED = (0.42, 0.45, 0.50)
ACCENT = (0.05, 0.32, 0.55)
ACCENT_DARK = (0.03, 0.20, 0.36)
ACCENT_TINT = (0.91, 0.945, 0.98)
BORDER = (0.79, 0.82, 0.85)
CODE_BG = (0.965, 0.972, 0.980)
ZEBRA = (0.975, 0.978, 0.982)
WHITE = (1, 1, 1)
GOOD = (0.09, 0.43, 0.24)
BAD = (0.66, 0.14, 0.14)
WARN = (0.71, 0.45, 0.05)

A4 = (595.28, 841.89)


def sanitize(text):
    for a, b in _TRANSLATE:
        text = text.replace(a, b)
    return text.encode('cp1252', 'replace').decode('cp1252')


def char_width(ch, style, size):
    table = FONTS[style][1]
    if table is None:                 # Courier is monospaced
        return 600 * size / 1000.0
    return table.get(ch, 556) * size / 1000.0


def text_width(s, style, size):
    return sum(char_width(c, style, size) for c in s)


def _esc(s):
    return (s.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)'))


# --------------------------------------------------------------------------
# Inline markup
# --------------------------------------------------------------------------

_RUN_RE = re.compile(r'(\*\*.+?\*\*|`[^`]+`)', re.S)


def parse_runs(text, base='r'):
    """'plain **bold** and `code`' -> [(text, style), ...]"""
    out = []
    for part in _RUN_RE.split(text):
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) > 4:
            out.append((part[2:-2], 'b'))
        elif part.startswith('`') and part.endswith('`') and len(part) > 2:
            out.append((part[1:-1], 'c'))
        else:
            out.append((part, base))
    return out


def tokenize(runs):
    """Flatten runs into [(word, style, space_before)] for wrapping."""
    tokens = []
    first = True
    for text, style in runs:
        leading_space = text[:1].isspace()
        for i, word in enumerate(text.split()):
            space_before = (not first) and (i > 0 or leading_space or bool(tokens))
            tokens.append((word, style, space_before and not first))
            first = False
    return tokens


def wrap_tokens(tokens, size, max_width):
    """-> list of lines, each a list of (word, style, x_offset)."""
    lines, line, x = [], [], 0.0
    for word, style, space_before in tokens:
        sp = char_width(' ', style, size) if (space_before and line) else 0.0
        w = text_width(word, style, size)
        if line and x + sp + w > max_width:
            lines.append(line)
            line, x = [], 0.0
            sp = 0.0
        line.append((word, style, x + sp))
        x += sp + w
    if line:
        lines.append(line)
    return lines


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------

class Document(object):

    def __init__(self, page_size=A4, margin=54, footer_text=''):
        self.pw, self.ph = page_size
        self.margin = margin
        self.footer_text = footer_text
        self.left = margin
        self.right = self.pw - margin
        self.top = self.ph - margin
        self.bottom = margin + 26          # room for the footer
        self.width = self.right - self.left
        self._pages = []
        self._ops = None
        self.y = 0.0
        self._page_no = 0
        self._suppress_footer = False
        self.new_page(first=True)

    # -- low level ---------------------------------------------------------

    def _op(self, s):
        self._ops.append(s)

    def _fill(self, color):
        self._op('%.3f %.3f %.3f rg' % color)

    def _stroke(self, color):
        self._op('%.3f %.3f %.3f RG' % color)

    def rect(self, x, y, w, h, color, stroke=None, line_width=0.6):
        self._fill(color)
        if stroke:
            self._stroke(stroke)
            self._op('%.2f w' % line_width)
            self._op('%.2f %.2f %.2f %.2f re B' % (x, y, w, h))
        else:
            self._op('%.2f %.2f %.2f %.2f re f' % (x, y, w, h))

    def line(self, x1, y1, x2, y2, color=BORDER, width=0.6):
        self._stroke(color)
        self._op('%.2f w' % width)
        self._op('%.2f %.2f m %.2f %.2f l S' % (x1, y1, x2, y2))

    def draw_text(self, x, y, s, style='r', size=10, color=INK):
        s = sanitize(s)
        if not s:
            return
        self._fill(color)
        self._op('BT /%s %.2f Tf %.2f %.2f Td (%s) Tj ET'
                 % (FONTS[style][0], size, x, y, _esc(s)))

    # -- page management ---------------------------------------------------

    def new_page(self, first=False):
        if self._ops is not None:
            self._finish_page()
        self._ops = []
        self._page_no += 1
        self.y = self.top

    def _finish_page(self):
        if not self._suppress_footer and self._page_no > 1:
            self.line(self.left, self.margin + 16, self.right, self.margin + 16,
                      BORDER, 0.5)
            self.draw_text(self.left, self.margin + 5, self.footer_text,
                           'r', 7.5, MUTED)
            label = 'Page %d' % self._page_no
            self.draw_text(self.right - text_width(label, 'r', 7.5),
                           self.margin + 5, label, 'r', 7.5, MUTED)
        self._pages.append('\n'.join(self._ops))
        self._ops = None

    def ensure(self, height):
        if self.y - height < self.bottom:
            self.new_page()
            return True
        return False

    def space(self, h=8):
        self.y -= h

    # -- block elements ----------------------------------------------------

    def cover_band(self, height=170):
        """Full-bleed accent band at the top of the current page."""
        self.rect(0, self.ph - height, self.pw, height, ACCENT)

    def title_block(self, kicker, title_lines, subtitle, meta_lines):
        self._suppress_footer = True
        self.cover_band(200)
        y = self.ph - 62
        self.draw_text(self.left, y, kicker.upper(), 'b', 9.5, (0.72, 0.83, 0.92))
        y -= 34
        for ln in title_lines:
            self.draw_text(self.left, y, ln, 'b', 25, WHITE)
            y -= 30
        y -= 6
        self.draw_text(self.left, y, subtitle, 'r', 12, (0.85, 0.90, 0.95))

        self.y = self.ph - 232
        for label, value in meta_lines:
            self.draw_text(self.left, self.y, label, 'b', 9, ACCENT)
            self.draw_text(self.left + 96, self.y, value, 'r', 9, INK)
            self.y -= 16
        self.space(6)
        self.line(self.left, self.y, self.right, self.y, BORDER, 0.8)
        self.space(16)

    def h1(self, text, number=None):
        self.ensure(78)
        self.space(10)
        label = ('%s  %s' % (number, text)) if number else text
        self.rect(self.left, self.y - 4, 3.2, 20, ACCENT)
        self.draw_text(self.left + 12, self.y, label, 'b', 15.5, ACCENT_DARK)
        self.y -= 12
        self.space(12)

    def h2(self, text):
        self.ensure(58)
        self.space(8)
        self.draw_text(self.left, self.y, text, 'b', 11.6, INK)
        self.y -= 6
        self.line(self.left, self.y, self.right, self.y, BORDER, 0.5)
        self.space(11)

    def h3(self, text):
        self.ensure(44)
        self.space(6)
        self.draw_text(self.left, self.y, text, 'b', 10, ACCENT)
        self.space(13)

    def para(self, text, size=9.6, leading=13.4, color=INK, indent=0,
             base='r', space_after=7):
        tokens = tokenize(parse_runs(text, base))
        lines = wrap_tokens(tokens, size, self.width - indent)
        for ln in lines:
            self.ensure(leading)
            for word, style, dx in ln:
                self.draw_text(self.left + indent + dx, self.y, word, style,
                               size, color)
            self.y -= leading
        self.space(space_after)

    def bullets(self, items, size=9.6, leading=13.2, bullet='\u2022',
                indent=14, gap=6, space_after=8):
        for item in items:
            tokens = tokenize(parse_runs(item))
            lines = wrap_tokens(tokens, size, self.width - indent - 4)
            for i, ln in enumerate(lines):
                self.ensure(leading)
                if i == 0:
                    self.draw_text(self.left + 3, self.y, bullet, 'r', size, ACCENT)
                for word, style, dx in ln:
                    self.draw_text(self.left + indent + dx, self.y, word,
                                   style, size, INK)
                self.y -= leading
            self.space(gap * 0.35)
        self.space(space_after)

    def numbered(self, items, size=9.6, leading=13.2, indent=20, space_after=8):
        for n, item in enumerate(items, 1):
            tokens = tokenize(parse_runs(item))
            lines = wrap_tokens(tokens, size, self.width - indent - 4)
            for i, ln in enumerate(lines):
                self.ensure(leading)
                if i == 0:
                    self.draw_text(self.left + 3, self.y, '%d.' % n, 'b',
                                   size, ACCENT)
                for word, style, dx in ln:
                    self.draw_text(self.left + indent + dx, self.y, word,
                                   style, size, INK)
                self.y -= leading
            self.space(2)
        self.space(space_after)

    def code(self, text, size=7.6, leading=10.0, pad=8, space_after=10):
        raw_lines = [ln.rstrip() for ln in text.strip('\n').split('\n')]
        # Hard-wrap over-long lines at the box width.
        max_chars = int((self.width - 2 * pad - 4) / (600 * size / 1000.0))
        lines = []
        for ln in raw_lines:
            if len(ln) <= max_chars:
                lines.append(ln)
            else:
                stub = ln
                lead = len(ln) - len(ln.lstrip())
                while len(stub) > max_chars:
                    cut = stub.rfind(' ', 0, max_chars)
                    if cut <= lead:
                        cut = max_chars
                    lines.append(stub[:cut])
                    stub = ' ' * (lead + 4) + stub[cut:].lstrip()
                lines.append(stub)

        i = 0
        while i < len(lines):
            remaining = int((self.y - self.bottom - 2 * pad) / leading)
            if remaining < 3:
                self.new_page()
                remaining = int((self.y - self.bottom - 2 * pad) / leading)
            chunk = lines[i:i + remaining]
            box_h = len(chunk) * leading + 2 * pad - (leading - size) + 2
            self.rect(self.left, self.y - box_h + leading - 2, self.width,
                      box_h, CODE_BG, BORDER, 0.5)
            self.rect(self.left, self.y - box_h + leading - 2, 2.2, box_h,
                      (0.62, 0.70, 0.78))
            ty = self.y - pad + 2
            for ln in chunk:
                self.draw_text(self.left + pad + 4, ty, ln, 'c', size,
                               (0.16, 0.20, 0.26))
                ty -= leading
            self.y = self.y - box_h + leading - 2 - 2
            i += len(chunk)
        self.space(space_after)

    def callout(self, text, label=None, accent=ACCENT, tint=ACCENT_TINT,
                size=9.4, leading=13.0, pad=9, space_after=10):
        inner = self.width - 2 * pad - 10
        blocks = []
        if label:
            blocks.append((label, 'b', 9.4))
        blocks.append((text, 'r', size))

        laid = []
        total_h = 2 * pad
        for bi, (txt, base, sz) in enumerate(blocks):
            lines = wrap_tokens(tokenize(parse_runs(txt, base)), sz, inner)
            is_label = bool(label) and bi == 0
            laid.append((lines, sz, is_label))
            total_h += len(lines) * leading
        if len(blocks) > 1:
            total_h += 3

        if self.y - total_h < self.bottom:
            self.new_page()

        top_y = self.y + size - 2
        self.rect(self.left, top_y - total_h, self.width, total_h, tint)
        self.rect(self.left, top_y - total_h, 3.0, total_h, accent)

        ty = self.y - pad + 3
        for lines, sz, is_label in laid:
            for ln in lines:
                for word, style, dx in ln:
                    col = accent if is_label else INK
                    self.draw_text(self.left + pad + 8 + dx, ty, word, style,
                                   sz, col)
                ty -= leading
            ty -= 3
        self.y = top_y - total_h - 2
        self.space(space_after)

    def table(self, headers, rows, widths=None, size=8.2, header_size=8.2,
              leading=10.6, pad=5, aligns=None, zebra=True, space_after=12,
              cell_styles=None):
        """
        widths: relative column weights (normalised to the content width).
        aligns: per-column 'l' | 'r' | 'c'.
        cell_styles: optional dict {(row_idx, col_idx): (style, color)}.
        """
        ncols = len(headers)
        if widths is None:
            widths = [1] * ncols
        total = float(sum(widths))
        colw = [self.width * w / total for w in widths]
        if aligns is None:
            aligns = ['l'] * ncols
        cell_styles = cell_styles or {}

        xs, acc = [], self.left
        for w in colw:
            xs.append(acc)
            acc += w

        def cell_lines(txt, ci, style_base='r', sz=None):
            sz = sz or size
            return wrap_tokens(tokenize(parse_runs(str(txt), style_base)), sz,
                               colw[ci] - 2 * pad)

        def draw_row(cells, ri, is_header):
            wrapped, maxlines = [], 1
            for ci, val in enumerate(cells):
                base = 'b' if is_header else \
                    cell_styles.get((ri, ci), ('r', INK))[0]
                sz = header_size if is_header else size
                lines = cell_lines(val, ci, base, sz)
                wrapped.append((lines, base, sz))
                maxlines = max(maxlines, len(lines))
            row_h = maxlines * leading + 2 * pad - (leading - size) + 1

            if self.y - row_h < self.bottom:
                return None, row_h

            if is_header:
                self.rect(self.left, self.y - row_h + leading - 2, self.width,
                          row_h, ACCENT)
            elif zebra and ri % 2 == 1:
                self.rect(self.left, self.y - row_h + leading - 2, self.width,
                          row_h, ZEBRA)

            for ci, (lines, base, sz) in enumerate(wrapped):
                color = WHITE if is_header else \
                    cell_styles.get((ri, ci), ('r', INK))[1]
                ty = self.y - pad + 3
                for ln in lines:
                    line_w = 0.0
                    if ln:
                        last_word, last_style, last_dx = ln[-1]
                        line_w = last_dx + text_width(last_word, last_style, sz)
                    if aligns[ci] == 'r':
                        x0 = xs[ci] + colw[ci] - pad - line_w
                    elif aligns[ci] == 'c':
                        x0 = xs[ci] + (colw[ci] - line_w) / 2.0
                    else:
                        x0 = xs[ci] + pad
                    for word, style, dx in ln:
                        self.draw_text(x0 + dx, ty, word, style, sz, color)
                    ty -= leading

            bottom_y = self.y - row_h + leading - 2
            if not is_header:
                self.line(self.left, bottom_y, self.right, bottom_y,
                          (0.88, 0.90, 0.92), 0.5)
            self.y = bottom_y
            return True, row_h

        ok, h = draw_row(headers, -1, True)
        if ok is None:
            self.new_page()
            draw_row(headers, -1, True)

        for ri, row in enumerate(rows):
            ok, h = draw_row(row, ri, False)
            if ok is None:
                self.new_page()
                draw_row(headers, -1, True)
                draw_row(row, ri, False)

        self.space(space_after)

    def kpi_strip(self, items, height=46, space_after=12):
        """items: [(label, value, color)]"""
        self.ensure(height + 10)
        n = len(items)
        gap = 8
        w = (self.width - gap * (n - 1)) / n
        top_y = self.y + 8
        for i, (label, value, color) in enumerate(items):
            x = self.left + i * (w + gap)
            self.rect(x, top_y - height, w, height, ACCENT_TINT)
            self.rect(x, top_y - height, w, 2.4, color)
            self.draw_text(x + 8, top_y - 17, label.upper(), 'b', 6.8, MUTED)
            self.draw_text(x + 8, top_y - 34, value, 'b', 13, color)
        self.y = top_y - height - 4
        self.space(space_after)

    def rule(self, space_before=4, space_after=10, color=BORDER):
        self.space(space_before)
        self.ensure(4)
        self.line(self.left, self.y, self.right, self.y, color, 0.6)
        self.space(space_after)

    def page_break(self):
        self.new_page()

    # -- output ------------------------------------------------------------

    def save(self, path):
        if self._ops is not None:
            self._finish_page()

        objects = []          # list of byte strings, index 0 -> object 1

        def add(body):
            objects.append(body)
            return len(objects)

        catalog_num = add(b'')                       # 1, patched later
        pages_num = add(b'')                         # 2, patched later
        font_nums = {}
        for res, base in _BASE_FONTS:
            font_nums[res] = add(
                ('<< /Type /Font /Subtype /Type1 /BaseFont /%s '
                 '/Encoding /WinAnsiEncoding >>' % base).encode('latin-1'))

        font_res = ' '.join('/%s %d 0 R' % (r, font_nums[r])
                            for r, _ in _BASE_FONTS)

        page_nums = []
        for content in self._pages:
            data = content.encode('latin-1', 'replace')
            stream = add(b'<< /Length %d >>\nstream\n' % len(data) + data
                         + b'\nendstream')
            page = add(
                ('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] '
                 '/Resources << /Font << %s >> >> /Contents %d 0 R >>'
                 % (pages_num, self.pw, self.ph, font_res, stream)
                 ).encode('latin-1'))
            page_nums.append(page)

        kids = ' '.join('%d 0 R' % n for n in page_nums)
        objects[pages_num - 1] = (
            '<< /Type /Pages /Count %d /Kids [%s] >>'
            % (len(page_nums), kids)).encode('latin-1')
        objects[catalog_num - 1] = (
            '<< /Type /Catalog /Pages %d 0 R >>' % pages_num).encode('latin-1')

        out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = []
        for i, body in enumerate(objects, 1):
            offsets.append(len(out))
            out += b'%d 0 obj\n' % i + body + b'\nendobj\n'

        xref_at = len(out)
        out += b'xref\n0 %d\n' % (len(objects) + 1)
        out += b'0000000000 65535 f \n'
        for off in offsets:
            out += b'%010d 00000 n \n' % off
        out += (b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n'
                % (len(objects) + 1, catalog_num, xref_at))

        with open(path, 'wb') as f:
            f.write(bytes(out))
        return len(page_nums)
