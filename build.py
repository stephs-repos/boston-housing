"""Rebuild the map from scratch: fetch sources, join them per ZIP, write out/boston-housing-map.html.

    uv run build.py              # reuse anything already downloaded into data/raw
    uv run build.py --refresh    # download every source again
"""
import datetime, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
RAW, BUILD, OUT = ROOT / 'data/raw', ROOT / 'data/build', ROOT / 'out'
sys.path.insert(0, str(ROOT / 'pipeline'))
from config import ACS_YEAR, FBI_YEAR, SAFMR_FY  # noqa: E402

D3 = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js'


def run(stage, *args):
    t = time.time()
    print(f'[{stage}]', flush=True)
    subprocess.run([sys.executable, str(ROOT / 'pipeline' / f'{stage}.py'), *map(str, args)], check=True)
    print(f'[{stage}] {time.time() - t:.0f}s')


def page():
    data = json.loads((BUILD / 'layers.json').read_text())
    osm = datetime.date.fromisoformat(data['layersAsOf']['osm']).strftime('%B %Y')
    web = {n: (ROOT / 'web' / n).read_text() for n in ('head.html', 'body.html', 'app.js')}
    html = (f"{web['head.html']}{web['body.html']}<script src=\"{D3}\"></script>\n"
            f"<script>const DATA={json.dumps(data, separators=(',', ':'))};\n{web['app.js']}</script>\n")
    for key, val in {'SAFMR_FY': SAFMR_FY, 'FBI_YEAR': FBI_YEAR, 'OSM_DATE': osm, 'ACS_SPAN': f'{ACS_YEAR - 4}–{ACS_YEAR}'}.items():
        html = html.replace('{{' + key + '}}', str(val))
    OUT.mkdir(exist_ok=True)
    (OUT / 'boston-housing-map.html').write_text(html)
    print(f'[page] out/boston-housing-map.html {len(html) // 1024} KB')


if __name__ == '__main__':
    BUILD.mkdir(parents=True, exist_ok=True)
    run('fetch', RAW, *(['--refresh'] if '--refresh' in sys.argv else []))
    run('base', RAW, BUILD)
    run('commute', RAW, BUILD)
    run('layers', RAW, BUILD)
    page()
