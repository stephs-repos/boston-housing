"""Weekday-morning transit+walk minutes from every MBTA stop to North Bennet Street School.

Static approximation from the GTFS timetable: median scheduled ride time between
consecutive stops, plus half the headway as wait each time you board a route.
Subway, light rail and bus only (what a monthly LinkPass covers)."""
import csv, datetime, heapq, json, math, statistics, sys
from collections import defaultdict

from config import SCHOOL

G = f'{sys.argv[1]}/gtfs'; OUT = f'{sys.argv[2]}/stop_minutes.json'
# the next Wednesday: a plain weekday inside the feed's current service period
_d = datetime.date.today() + datetime.timedelta(days=(2 - datetime.date.today().weekday()) % 7 or 7)
DATE, DOW = _d.strftime('%Y%m%d'), 'wednesday'
WINDOW = (7*3600, 9*3600 + 1800)
WALK_MPS = 1.3 / 1.25        # 1.3 m/s on a street grid ~25% longer than straight line
MAX_TRANSFER_WALK = 400      # m between stops
MAX_WAIT, MIN_WAIT = 15*60, 2*60

def m(a, b):
    dlat = math.radians(b[0]-a[0]); dlon = math.radians(b[1]-a[1])
    h = math.sin(dlat/2)**2 + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def secs(t):
    h, mi, s = map(int, t.split(':')); return h*3600 + mi*60 + s

services = {r['service_id'] for r in csv.DictReader(open(f'{G}/calendar.txt'))
            if r[DOW] == '1' and r['start_date'] <= DATE <= r['end_date']}
for r in csv.DictReader(open(f'{G}/calendar_dates.txt')):
    if r['date'] == DATE:
        (services.add if r['exception_type'] == '1' else services.discard)(r['service_id'])
rtype = {r['route_id']: r['route_type'] for r in csv.DictReader(open(f'{G}/routes.txt'))}
trips = {r['trip_id']: r['route_id'] for r in csv.DictReader(open(f'{G}/trips.txt'))
         if r['service_id'] in services and rtype.get(r['route_id']) in ('0', '1', '3')}

stops = {}
parent = {}
for r in csv.DictReader(open(f'{G}/stops.txt')):
    if r['stop_lat']:
        stops[r['stop_id']] = (float(r['stop_lat']), float(r['stop_lon']))
        parent[r['stop_id']] = r['parent_station'] or r['stop_id']

ride = defaultdict(list)          # (from, to, route) -> [seconds]
deps = defaultdict(list)          # (stop, route) -> [departure secs]
prev = {}
for r in csv.DictReader(open(f'{G}/stop_times.txt')):
    route = trips.get(r['trip_id'])
    if not route: continue
    t = secs(r['departure_time'])
    p = prev.get(r['trip_id'])
    if p and WINDOW[0] <= p[1] <= WINDOW[1]:
        ride[(p[0], r['stop_id'], route)].append(secs(r['arrival_time']) - p[1])
    if WINDOW[0] <= t <= WINDOW[1]:
        deps[(r['stop_id'], route)].append(t)
    prev[r['trip_id']] = (r['stop_id'], t)

def wait(stop, route):
    d = sorted(set(deps.get((stop, route), [])))
    if len(d) < 2: return MAX_WAIT
    return max(MIN_WAIT, min(MAX_WAIT, (WINDOW[1]-WINDOW[0]) / len(d) / 2))

# Reverse graph: edges point from destination side back to origin side.
rev = defaultdict(list)
for (a, b, route), ts in ride.items():
    rev[('R', b, route)].append((('R', a, route), statistics.median(ts)))
    rev[('S', b)].append((('R', b, route), 0))                 # alight
for (s, route) in deps:
    rev[('R', s, route)].append((('S', s), wait(s, route)))   # board
used = {s for k in deps for s in [k[0]]} | {k[1] for k in ride}
grid = defaultdict(list)
for s in used:
    lat, lon = stops[s]; grid[(round(lat, 2), round(lon, 2))].append(s)
for s in used:
    lat, lon = stops[s]
    for dl in (-0.01, 0, 0.01):
        for dn in (-0.01, 0, 0.01):
            for o in grid.get((round(lat+dl, 2), round(lon+dn, 2)), []):
                d = m(stops[s], stops[o])
                if o != s and d <= MAX_TRANSFER_WALK:
                    rev[('S', s)].append((('S', o), d / WALK_MPS))

dist = {}
pq = []
for s in used:
    d = m(stops[s], SCHOOL)
    if d <= 1200: heapq.heappush(pq, (d / WALK_MPS, ('S', s)))
while pq:
    c, n = heapq.heappop(pq)
    if n in dist: continue
    dist[n] = c
    for nb, w in rev.get(n, []):
        if nb not in dist: heapq.heappush(pq, (c + w, nb))

out = [[round(stops[s][1], 5), round(stops[s][0], 5), round(dist[('S', s)] / 60, 1)] for s in used if ('S', s) in dist]
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print(DATE, len(services), 'services', len(trips), 'trips', len(used), 'stops reached', len(out))
for name, pt in [('Malden Ctr', (42.4267, -71.0743)), ('Revere Wonderland', (42.4134, -70.9916)), ('Chelsea', (42.3918, -71.0336)), ('Ashmont', (42.2846, -71.0640)), ('Davis', (42.3967, -71.1218))]:
    best = min(out, key=lambda o: m(pt, (o[1], o[0])))
    print(name, best[2], 'min')
