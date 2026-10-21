"""Join Zillow ZORI + HUD SAFMR FY27 to MA ZIP polygons near NBSS; add MBTA rapid transit."""
import csv, json, math, sys
import openpyxl

from config import SCHOOL

DL = sys.argv[1]; OUT = f'{sys.argv[2]}/base.json'
RADIUS_KM = 26

def km(a, b):
    dlat = math.radians(b[0]-a[0]); dlon = math.radians(b[1]-a[1])
    h = math.sin(dlat/2)**2 + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2
    return 6371*2*math.asin(math.sqrt(h))

def simplify(pts, tol=0.0004):
    # Douglas-Peucker on lon/lat
    if len(pts) < 4: return pts
    def d(p, a, b):
        if a == b: return math.dist(p, a)
        (x, y), (x1, y1), (x2, y2) = p, a, b
        return abs((y2-y1)*x-(x2-x1)*y+x2*y1-y2*x1)/math.dist(a, b)
    i, dmax = 0, 0
    for k in range(1, len(pts)-1):
        dk = d(pts[k], pts[0], pts[-1])
        if dk > dmax: i, dmax = k, dk
    if dmax > tol:
        return simplify(pts[:i+1], tol)[:-1] + simplify(pts[i:], tol)
    return [pts[0], pts[-1]]

def rings(geom):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    out = []
    for poly in polys:
        p = []
        for ring in poly:
            r = [[round(x, 4), round(y, 4)] for x, y in simplify(ring)]
            if len(r) >= 4: p.append(r)
        if p: out.append(p)
    return out

zori = {r['RegionName'].zfill(5): r for r in csv.DictReader(open(f'{DL}/zori_zip.csv'))}
months = [c for c in next(iter(zori.values())).keys() if c[:2] == '20']
last, yago = months[-1], months[-13]

safmr = {}
ws = openpyxl.load_workbook(f'{DL}/safmr.xlsx', read_only=True).active
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0] and str(row[0]).startswith(('01', '02')):
        safmr[str(row[0]).zfill(5)] = dict(b0=row[3], b1=row[6], b2=row[9], b3=row[12], b4=row[15])

geo = json.load(open(f'{DL}/ma_zips.json'))
feats = []
for f in geo['features']:
    z = f['properties']['ZCTA5CE10']
    lon = f['properties'].get('INTPTLON10'); lat = f['properties'].get('INTPTLAT10')
    c = (float(lat), float(lon))
    dist = km(SCHOOL, c)
    if dist > RADIUS_KM: continue
    zr, sf = zori.get(z), safmr.get(z)
    v, v0 = (zr or {}).get(last), (zr or {}).get(yago)
    props = dict(zip=z, city=(zr or {}).get('City') or '', km=round(dist, 1),
                 zori=round(float(v)) if v else None,
                 yoy=round((float(v)/float(v0)-1)*100, 1) if v and v0 else None)
    if sf:
        props.update(sf)
        props['room'] = round(sf['b3']/3)  # per-bedroom share of a 3BR
    feats.append(dict(type='Feature', properties=props, geometry=dict(type='MultiPolygon', coordinates=rings(f['geometry']))))

def decode(poly):
    pts, i, lat, lng = [], 0, 0, 0
    while i < len(poly):
        vals = []
        for _ in range(2):
            shift = res = 0
            while True:
                b = ord(poly[i]) - 63; i += 1
                res |= (b & 0x1f) << shift; shift += 5
                if b < 0x20: break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        lat += vals[0]; lng += vals[1]
        pts.append([round(lng/1e5, 5), round(lat/1e5, 5)])
    return pts

COLORS = {'Red': '#DA291C', 'Mattapan': '#DA291C', 'Orange': '#ED8B00', 'Blue': '#003DA5', '741': '#7C878E', '742': '#7C878E'}
lines = []
for r in ['Red', 'Orange', 'Blue', 'Green-B', 'Green-C', 'Green-D', 'Green-E', 'Mattapan', '741', '742']:
    seen = set()
    for s in json.load(open(f'{DL}/shapes_{r}.json'))['data']:
        pts = decode(s['attributes']['polyline'])
        key = (tuple(pts[0]), tuple(pts[-1]))
        if key in seen or (key[1], key[0]) in seen: continue
        seen.add(key)
        lines.append(dict(route=r, color=COLORS.get(r, '#00843D'), pts=[[round(x, 4), round(y, 4)] for x, y in simplify(pts, 0.0002)]))
stations = {}
for s in json.load(open(f'{DL}/stops.json'))['data']:
    a = s['attributes']
    if a['location_type'] == 1 or not a.get('parent_station'):
        stations[a['name']] = [round(a['longitude'], 5), round(a['latitude'], 5)]

json.dump(dict(asof=last, yago=yago, school=[SCHOOL[1], SCHOOL[0]], zips=dict(type='FeatureCollection', features=feats),
               lines=lines, stations=[[n, *c] for n, c in stations.items()]), open(OUT, 'w'), separators=(',', ':'))
n = len(feats); nz = sum(1 for f in feats if f['properties']['zori']); ns = sum(1 for f in feats if 'b1' in f['properties'])
print(f'{n} ZIPs, {nz} with Zillow, {ns} with HUD, {len(lines)} line shapes, {len(stations)} stations, asof {last}')
