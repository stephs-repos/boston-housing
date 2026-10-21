"""Add crime, commute, census and amenity layers to data.json (per ZIP)."""
import csv, json, math, statistics, sys
from collections import defaultdict, Counter
import openpyxl

from config import ACS_YEAR, CRIME_YEAR, FBI_YEAR

D, BUILD = sys.argv[1], sys.argv[2]
data = json.load(open(f'{BUILD}/base.json'))
feats = data['zips']['features']
WALK_MPM = 1.3 / 1.25 * 60  # metres per minute on streets
SHED = 1000                  # metres: a ~12 minute walk

def m(a, b):  # (lon, lat)
    dlat = math.radians(b[1]-a[1]); dlon = math.radians(b[0]-a[0])
    h = math.sin(dlat/2)**2 + math.cos(math.radians(a[1]))*math.cos(math.radians(b[1]))*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def inside(pt, mpoly):
    x, y = pt; hit = False
    for poly in mpoly:
        for k, ring in enumerate(poly):
            c = False
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1) + x1: c = not c
            if c: hit = not hit if k else True
    return hit

class Grid:  # bucket points by ~1km cells for radius queries
    def __init__(self, pts): 
        self.b = defaultdict(list)
        for p in pts: self.b[(int(p[1]/0.009), int(p[0]/0.012))].append(p)
    def near(self, pt, r):
        cy, cx = int(pt[1]/0.009), int(pt[0]/0.012); k = int(r/900) + 1
        for dy in range(-k, k+1):
            for dx in range(-k, k+1):
                for p in self.b.get((cy+dy, cx+dx), []):
                    d = m(pt, p)
                    if d <= r: yield p, d

def samples(f):
    coords = [c for poly in f['geometry']['coordinates'] for c in poly[0]]
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    step = 0.0045
    while True:
        pts = [(x, y) for i in range(int((max(xs)-min(xs))/(step*1.33))+2) for j in range(int((max(ys)-min(ys))/step)+2)
               for x, y in [(min(xs)+i*step*1.33, min(ys)+j*step)] if inside((x, y), f['geometry']['coordinates'])]
        if len(pts) <= 60: break
        step *= 1.3
    return pts or [tuple(f['properties']['c'] if 'c' in f['properties'] else coords[0])]

for f in feats: f['_s'] = samples(f)

# --- commute: median over the ZIP of (walk to stop + timetable minutes), or walk straight to school
stops = Grid([(lon, lat, mins) for lon, lat, mins in json.load(open(f'{BUILD}/stop_minutes.json'))])
school = tuple(data['school'])
for f in feats:
    best = []
    for s in f['_s']:
        t = m(s, school) / WALK_MPM
        for p, d in stops.near(s, 1200): t = min(t, d / WALK_MPM + p[2])
        best.append(t)
    f['properties']['commute'] = round(statistics.median(best))

# --- ACS 5-year
def acs(t):
    rows = csv.DictReader(open(f'{D}/acs_{t}.txt'), delimiter='|')
    return {r['GEO_ID'][-5:]: r for r in rows}
pop, age, ten, mode, beds = acs('b01003'), acs('b01001'), acs('b25003'), acs('b08301'), acs('b25042')
num = lambda r, *cols: sum(max(0, int(r[f'{c}'])) for c in cols)
for f in feats:
    p, z = f['properties'], f['properties']['zip']
    p['pop'] = int(pop[z]['B01003_E001']) if z in pop else 0
    if z in age and int(age[z]['B01001_E001']) > 0:
        yc = [f'B01001_E0{n:02d}' for n in (8, 9, 10, 11, 12, 32, 33, 34, 35, 36)]
        p['young'] = round(100 * num(age[z], *yc) / int(age[z]['B01001_E001']))
    if z in ten and int(ten[z]['B25003_E001']) > 0:
        p['renters'] = round(100 * int(ten[z]['B25003_E003']) / int(ten[z]['B25003_E001']))
    if z in beds and p.get('b0') is not None:
        # HUD rent averaged over this ZIP's own mix of rental units by bedroom count (5+ priced as 4).
        # Zillow's all-sizes index is compared against this, so ZIPs of small units aren't read as cheap.
        r = beds[z]; n = [max(0, int(r[f'B25042_E0{k}'])) for k in range(10, 16)]
        if sum(n) >= 100:
            hud = [p['b0'], p['b1'], p['b2'], p['b3'], p['b4'], p['b4']]
            p['hudMix'] = round(sum(c * h for c, h in zip(n, hud)) / sum(n))
    if z in mode:
        r = mode[z]; base = int(r['B08301_E001']) - int(r['B08301_E021'])
        if base > 0: p['carfree'] = round(100 * num(r, 'B08301_E010', 'B08301_E018', 'B08301_E019') / base)

# --- town for each ZIP (largest land overlap)
town = {}
for r in csv.DictReader(open(f'{D}/rel_cousub.txt', encoding='utf-8-sig'), delimiter='|'):
    z = r['GEOID_ZCTA5_20']
    if z and r['GEOID_COUSUB_20'].startswith('25'):
        a = int(r['AREALAND_PART'] or 0)
        if z not in town or a > town[z][1]:
            town[z] = (r['NAMELSAD_COUSUB_20'].replace(' Town city', '').replace(' city', '').replace(' town', ''), a)
for f in feats: f['properties']['town'] = town.get(f['properties']['zip'], ('', 0))[0]

# --- FBI Crime in the United States, Table 8 (city level)
fbi = {}
st = None
ws = openpyxl.load_workbook(f'{D}/fbi_table8.xlsx', read_only=True).active
for r in ws.iter_rows(min_row=5, values_only=True):
    st = r[0] or st
    if st == 'Massachusetts' and r[1] and r[2]:
        fbi[str(r[1]).rstrip('0123456789,')] = dict(pop=r[2], viol=r[3], prop=r[8])

# --- Boston: split the city's FBI totals across its ZIPs by where incidents happened (2025)
VIOL = ('ASSAULT - AGGRAVATED', 'ROBBERY', 'MURDER')
PROP = ('LARCENY', 'BURGLARY', 'AUTO THEFT', 'BREAKING AND ENTERING', 'ARSON')
bos = [f for f in feats if f['properties']['town'] == 'Boston']
cnt = defaultdict(Counter)
bb = Grid([])
for r in csv.DictReader(open(f'{D}/boston_crime.csv', encoding='utf-8-sig')):
    if r['YEAR'] != CRIME_YEAR or not r['Lat']: continue
    d = r['OFFENSE_DESCRIPTION'].strip()
    kind = 'viol' if d.startswith(VIOL) else 'prop' if d.startswith(PROP) else None
    if not kind: continue
    pt = (float(r['Long']), float(r['Lat']))
    if pt[1] < 42: continue
    for f in bos:
        if inside(pt, f['geometry']['coordinates']):
            cnt[f['properties']['zip']][kind] += 1; break
tot = Counter()
for c in cnt.values(): tot.update(c)
MIN_POP = 3000  # below this, per-resident rates mostly measure visitors
for f in feats:
    p = f['properties']
    if p['pop'] < MIN_POP: p['crimeNote'] = 'few residents'; continue
    if p['town'] == 'Boston':
        for k in ('viol', 'prop'):
            p[k] = round(cnt[p['zip']][k] / tot[k] * fbi['Boston'][k] / p['pop'] * 1000, 1)
        p['crimeSrc'] = 'zip'
    elif p['town'] in fbi:
        t = fbi[p['town']]
        p['viol'], p['prop'] = round(t['viol'] / t['pop'] * 1000, 1), round(t['prop'] / t['pop'] * 1000, 1)
        p['crimeSrc'] = 'town'
    else:
        p['crimeNote'] = 'no FBI report for ' + p['town']

# --- amenities within a 10-minute walk (median over the ZIP)
osm = json.load(open(f'{D}/osm.json'))['elements']
CATS = dict(music=('amenity', {'music_venue', 'nightclub', 'theatre', 'arts_centre'}), bars=('amenity', {'bar', 'pub'}),
            cafes=('amenity', {'cafe'}), grocery=('shop', {'supermarket', 'greengrocer'}),
            maker=('shop', {'hardware', 'doityourself'}), parks=('leisure', {'park'}))
pts = defaultdict(list)
for e in osm:
    t = e.get('tags', {}); c = e.get('center', e)
    if 'lat' not in c: continue
    for k, (tag, vals) in CATS.items():
        if t.get(tag) in vals or (k == 'maker' and t.get('leisure') == 'hackerspace'):
            pts[k].append((c['lon'], c['lat']))
bikes = [(s['lon'], s['lat']) for s in json.load(open(f'{D}/bluebikes.json'))['data']['stations']]
pts['bikes'] = bikes
for k, v in pts.items():
    g = Grid(v)
    for f in feats:
        f['properties'][k] = round(statistics.mean(sum(1 for _ in g.near(s, SHED)) for s in f["_s"]), 1)

for f in feats: del f['_s']; f['properties'].pop('c', None)
data['layersAsOf'] = dict(fbi=FBI_YEAR, acs=f'{ACS_YEAR - 4}–{ACS_YEAR}', osm=json.load(open(f'{D}/osm.json'))['osm3s']['timestamp_osm_base'][:10])
json.dump(data, open(f'{BUILD}/layers.json', 'w'), separators=(',', ':'))
print({k: len(v) for k, v in pts.items()}, 'boston incidents in zips', dict(tot))
print('towns without FBI:', sorted({f['properties']['town'] for f in feats if 'no FBI' in f['properties'].get('crimeNote', '')}))
print('low pop:', [(f['properties']['zip'], f['properties']['pop']) for f in feats if f['properties'].get('crimeNote') == 'few residents'])
