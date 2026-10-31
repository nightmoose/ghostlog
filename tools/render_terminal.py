"""Turn a captured `ghostlog summon` transcript into a terminal-style HTML page
(used only to make the README screenshot; the text is the real CLI output)."""

import sys
from html import escape
from pathlib import Path

src, cmd, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
rows = [f'<div class="cmd">$ {escape(cmd)}</div>']
for line in src.read_text().splitlines():
    s = line.strip()
    cls = "grey"
    if s.startswith("lineage:"):
        cls = "gold"
    elif line.startswith(("~", "   ")):
        cls = "bone"
    rows.append(f'<div class="{cls}">{escape(line) or "&nbsp;"}</div>')
out.write_text(
    "<!doctype html><meta charset=utf-8><style>"
    "body{margin:0;background:#0e0f14;font:20px/2.3 'DejaVu Sans Mono',monospace;"
    "padding:22px 40px;white-space:pre}.cmd{color:#a6e36b}.grey{color:#8b8b8b}"
    ".bone{color:#ece7ff}.gold{color:#f5a524}</style>" + "".join(rows)
)
