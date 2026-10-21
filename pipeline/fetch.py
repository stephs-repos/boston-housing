"""Download every source into data/raw. Each file is skipped if already present (use --refresh to redo)."""
import io, json, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

from config import ACS_YEAR, BBOX, FBI_YEAR, SAFMR_FY

RAW = Path(sys.argv[1]); RAW.mkdir(parents=True, exist_ok=True)
REFRESH = '--refresh' in sys.argv
# HUD and the FBI's download service turn away requests without a browser-like user agent.
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'}


def get(url, data=None, headers=UA):
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def step(name, fn):
    out = RAW / name
    if out.exists() and not REFRESH:
        print(f'  have  {name}'); return
    print(f'  fetch {name}', flush=True)
    body = fn()
    if body is not None:
        out.write_bytes(body)


def zori():
    return get('https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv')


def zip_shapes():
    return get('https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/ma_massachusetts_zip_codes_geo.min.json')


def safmr():
    # HUD's file naming changes from year to year; try the known spellings.
    base = f'https://www.huduser.gov/portal/datasets/fmr/fmr{SAFMR_FY}/'
    for name in [f'FY{SAFMR_FY % 100}_safmrs.xlsx', f'fy{SAFMR_FY}_safmrs_revised.xlsx', f'fy{SAFMR_FY}_safmrs.xlsx']:
        body = get(base + name)
        if body[:2] == b'PK':
            return body
    raise SystemExit(f'No SAFMR workbook found under {base}; check HUD USER for the file name.')


def mbta(path):
    return lambda: get(f'https://api-v3.mbta.com/{path}')


def gtfs():
    zipfile.ZipFile(io.BytesIO(get('https://cdn.mbta.com/MBTA_GTFS.zip'))).extractall(RAW / 'gtfs')


def acs(table):
    # Census bulk summary files cover every geography; keep only MA ZIP codes (ZCTAs 01xxx/02xxx).
    url = f'https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}/table-based-SF/data/5YRData/acsdt5y{ACS_YEAR}-{table}.dat'
    lines = get(url).decode().splitlines()
    keep = [lines[0]] + [l for l in lines[1:] if l.startswith(('860Z200US01', '860Z200US02'))]
    return ('\n'.join(keep) + '\n').encode()


def zip_town():
    return get('https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_cousub20_natl.txt')


def fbi_table8():
    signed = json.loads(get(f'https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key=cius/{FBI_YEAR}/offenses-known-to-le-{FBI_YEAR}.zip'))
    z = zipfile.ZipFile(io.BytesIO(get(next(iter(signed.values())), headers={})))
    name = next(n for n in z.namelist() if 'Table_8_' in n)
    return z.read(name)


def boston_crime():
    pkg = json.loads(get('https://data.boston.gov/api/3/action/package_show?id=crime-incident-reports-august-2015-to-date-source-new-system'))
    res = next(r for r in pkg['result']['resources'] if (r['name'] or '').endswith('to Present'))
    # The portal redirects to a signed S3 link written as host:443. urllib then sends a Host header
    # with the port, the signature no longer matches and S3 answers 403, so follow it by hand.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a): return None
    try:
        urllib.request.build_opener(NoRedirect).open(urllib.request.Request(res['url'], headers=UA))
        raise SystemExit('Expected a redirect from data.boston.gov')
    except urllib.error.HTTPError as e:
        return get(e.headers['Location'].replace(':443/', '/'), headers={})


def osm():
    s, w, n, e = BBOX; b = f'({s},{w},{n},{e})'
    # Three small queries instead of one big one: busy public servers time out on the combined query.
    queries = [f'nwr["amenity"~"^(music_venue|nightclub|theatre|arts_centre|bar|pub|cafe|library)$"]{b};',
               f'nwr["shop"~"^(supermarket|greengrocer|hardware|doityourself)$"]{b};',
               f'nwr["leisure"~"^(hackerspace|park)$"]{b};']
    merged = None
    for q in queries:
        part = json.loads(overpass(f'[out:json][timeout:120];({q});out center tags;'))
        merged = merged or {k: v for k, v in part.items() if k != 'elements'} | {'elements': []}
        merged['elements'] += part['elements']
    return json.dumps(merged).encode()


def overpass(query):
    # Public Overpass servers are often busy; try each in turn, twice. They reject requests without a named user agent.
    body = urllib.parse.urlencode({'data': query}).encode()
    for attempt in range(2):
        for host in ['overpass-api.de', 'overpass.kumi.systems', 'overpass.private.coffee']:
            try:
                out = get(f'https://{host}/api/interpreter', data=body, headers={'User-Agent': 'boston-housing-map/0.1 (personal research)'})
                if out.lstrip().startswith(b'{'):
                    return out
                print(f'    {host} returned no JSON, trying the next server')
            except (urllib.error.URLError, TimeoutError) as err:
                print(f'    {host} failed ({err}), trying the next server')
        time.sleep(30)
    raise SystemExit('Every Overpass server failed; rerun later (downloads already done are kept).')


def bluebikes():
    return get('https://gbfs.lyft.com/gbfs/1.1/bos/en/station_information.json')


if __name__ == '__main__':
    step('zori_zip.csv', zori)
    step('ma_zips.json', zip_shapes)
    step('safmr.xlsx', safmr)
    for route in ['Red', 'Orange', 'Blue', 'Green-B', 'Green-C', 'Green-D', 'Green-E', 'Mattapan', '741', '742']:
        step(f'shapes_{route}.json', mbta(f'shapes?filter%5Broute%5D={route}'))
    step('stops.json', mbta('stops?filter%5Broute_type%5D=0,1'))
    step('gtfs', gtfs)
    for t in ['b01003', 'b01001', 'b25003', 'b08301', 'b25042']:
        step(f'acs_{t}.txt', lambda t=t: acs(t))
    step('rel_cousub.txt', zip_town)
    step('fbi_table8.xlsx', fbi_table8)
    step('boston_crime.csv', boston_crime)
    step('osm.json', osm)
    step('bluebikes.json', bluebikes)
