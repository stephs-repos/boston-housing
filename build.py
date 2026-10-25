"""Rebuild the map from scratch: fetch sources, join them per ZIP, write the page.

    uv run build.py              # reuse anything already downloaded into data/raw
    uv run build.py --refresh    # download every source again
    uv run build.py --deploy     # build, then publish out/site to GitHub Pages (gh-pages branch)

Writes out/boston-housing-map.html (a page body for Claude artifacts, which add their own
<html>/<head> wrapper) and out/site/index.html (a complete document for GitHub Pages).
"""
import datetime, hashlib, html, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent
RAW, BUILD, OUT = ROOT / 'data/raw', ROOT / 'data/build', ROOT / 'out'
sys.path.insert(0, str(ROOT / 'pipeline'))
from config import ACS_YEAR, FBI_YEAR, SAFMR_FY  # noqa: E402

D3 = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js'
SITE_URL = 'https://stephs-repos.github.io/boston-housing/'
SHARE_TITLE = 'Where to live while at North Bennet Street School'
SHARE_TEXT = ('Every ZIP within 16 miles of the school in Boston, mapped by rent, transit commute, reported crime, '
              'nightlife and who lives there. Built from public data; set a budget and see what fits.')


def run(stage, *args):
    t = time.time()
    print(f'[{stage}]', flush=True)
    subprocess.run([sys.executable, str(ROOT / 'pipeline' / f'{stage}.py'), *map(str, args)], check=True)
    print(f'[{stage}] {time.time() - t:.0f}s')


def page():
    data = json.loads((BUILD / 'layers.json').read_text())
    data['fx'] = json.loads((RAW / 'fx.json').read_text())
    osm = datetime.date.fromisoformat(data['layersAsOf']['osm']).strftime('%B %Y')
    web = {n: (ROOT / 'web' / n).read_text() for n in ('head.html', 'body.html', 'app.js')}
    # Fill the year placeholders before the data goes in, so text inside the data is never treated as a placeholder.
    for key, val in {'SAFMR_FY': SAFMR_FY, 'FBI_YEAR': FBI_YEAR, 'OSM_DATE': osm, 'ACS_SPAN': f'{ACS_YEAR - 4}–{ACS_YEAR}'}.items():
        web = {n: t.replace('{{' + key + '}}', str(val)) for n, t in web.items()}
    # The data includes third-party strings (station and town names); escape <, > and & so none can close the <script>.
    blob = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    body = (f"{web['body.html']}<script src=\"{D3}\"></script>\n"
            f"<script>const DATA={blob};\n{web['app.js']}</script>\n")
    OUT.mkdir(exist_ok=True)
    (OUT / 'boston-housing-map.html').write_text(web['head.html'] + body)
    print(f"[page] out/boston-housing-map.html {len(web['head.html'] + body) // 1024} KB")
    site = OUT / 'site'
    site.mkdir(exist_ok=True)
    (site / 'index.html').write_text(document(web['head.html'], body))
    (site / '.nojekyll').write_text('')  # serve files as-is; skip GitHub's Jekyll step
    if (ROOT / 'web/og.png').exists():
        shutil.copy(ROOT / 'web/og.png', site / 'og.png')
    print('[page] out/site/index.html')


def document(head, body):
    # What the artifact host would otherwise add (doctype, charset, viewport, a small reset), plus the
    # Open Graph tags LinkedIn reads to draw the link preview.
    t, d = html.escape(SHARE_TITLE), html.escape(SHARE_TEXT)
    # LinkedIn caches preview images by URL for days; a content hash in the query makes a new image a new URL.
    og = ROOT / 'web/og.png'
    img = f"{SITE_URL}og.png?v={hashlib.sha256(og.read_bytes()).hexdigest()[:10]}" if og.exists() else ''
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{d}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="2400">
<meta property="og:image:height" content="1260">
<meta name="twitter:card" content="summary_large_image">
<style>:root{{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
body{{margin:0;font:14px/1.5 system-ui,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head}</head>
<body>
{body}</body>
</html>
"""


def deploy():
    # Push out/site as the only commit on gh-pages. The branch holds build output, so its history is not kept.
    origin = subprocess.run(['git', '-C', str(ROOT), 'remote', 'get-url', 'origin'],
                            capture_output=True, text=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(OUT / 'site', tmp, dirs_exist_ok=True)
        git = lambda *a: subprocess.run(['git', '-C', tmp, *a], check=True)  # noqa: E731
        git('init', '-q', '-b', 'gh-pages')
        git('add', '-A')
        git('commit', '-q', '-m', f'Deploy {datetime.datetime.now():%Y-%m-%d %H:%M}')
        git('push', '-q', '--force', origin, 'gh-pages')
    print(f'[deploy] pushed to gh-pages; live shortly at {SITE_URL}')


if __name__ == '__main__':
    BUILD.mkdir(parents=True, exist_ok=True)
    run('fetch', RAW, *(['--refresh'] if '--refresh' in sys.argv else []))
    run('base', RAW, BUILD)
    run('commute', RAW, BUILD)
    run('layers', RAW, BUILD)
    page()
    if '--deploy' in sys.argv:
        deploy()
