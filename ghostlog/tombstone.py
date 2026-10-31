"""Render the tombstone page: one self-contained HTML file, no network."""

from __future__ import annotations

from html import escape

from .lineage import Lineage
from .logparse import Remains
from .medium import Seance

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghostlog - Tombstone - {name}</title>
<style>
  :root {{ --night:#1a1020; --stone:#5c5c68; --marigold:#f5a524; --bone:#f3ead8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; background:var(--night); color:var(--bone);
         font-family:"DejaVu Sans Mono",ui-monospace,Menlo,Consolas,monospace;
         display:flex; flex-direction:column; align-items:center; }}
  h1 {{ color:var(--marigold); font-size:1.3rem; font-weight:normal; margin:1.6rem 0 1.2rem; }}
  .stone {{ width:min(400px,90vw); background:var(--stone); border:5px solid var(--marigold);
           border-radius:56px 56px 40px 40px; padding:2.2rem 1.5rem 2rem; text-align:center; }}
  .rip {{ font-size:3rem; margin:0 0 .4rem; letter-spacing:.05em; }}
  .name {{ font-size:1.3rem; margin:0 0 1rem; word-break:break-all; }}
  .years {{ font-size:1.1rem; margin:0 0 2.2rem; }}
  .epitaph p {{ margin:.9rem 0; }}
  .testimony {{ width:min(560px,92vw); margin:1.8rem 0 .6rem; line-height:1.6; }}
  .testimony p {{ margin:.2rem 0; }}
  .testimony p:first-child::before {{ content:"~ "; color:var(--marigold); }}
  .lineage {{ color:var(--marigold); width:min(560px,92vw); margin:.6rem 0; word-break:break-word; }}
  .voice {{ color:#9a93a3; font-size:.85rem; width:min(560px,92vw); margin:.4rem 0 1.4rem; }}
  .marigolds {{ display:flex; gap:38px; margin:auto 0 1.4rem; padding-top:1rem; }}
  .marigolds span {{ width:26px; height:26px; border-radius:50%; background:var(--marigold);
                     display:inline-block; }}
</style>
</head>
<body>
<h1>Ghostlog - Tombstone</h1>
<section class="stone" aria-label="tombstone">
  <p class="rip">R.I.P.</p>
  <p class="name">{name}</p>
  <p class="years">{years}</p>
  <div class="epitaph">{epitaph}</div>
</section>
<section class="testimony" aria-label="testimony">{testimony}</section>
<p class="lineage">lineage: {lineage}</p>
<p class="voice">voice: {voice} &middot; source: {source}</p>
<div class="marigolds" aria-hidden="true">{marigolds}</div>
</body>
</html>
"""


def render(remains: Remains, lineage: Lineage, seance: Seance) -> str:
    return _PAGE.format(
        name=escape(remains.job_name),
        years=escape(remains.lifespan),
        epitaph="".join(f"<p>{escape(line)}</p>" for line in seance.epitaph),
        testimony="".join(f"<p>{escape(line)}</p>" for line in seance.testimony),
        lineage=escape(lineage.describe()),
        voice=escape(seance.voice),
        source=escape(remains.source_path),
        marigolds="<span></span>" * 10,
    )
