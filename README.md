# boston-housing

Where to live while at North Bennet Street School (150 North St, Boston). A single HTML page maps every ZIP code within about 16 miles of the school by rent, transit commute, reported crime, nearby venues and amenities, and who lives there. It also has an adjustable best-fit score.

## Rebuild

```bash
uv run build.py              # reuses anything already downloaded into data/raw
uv run build.py --refresh    # downloads every source again
```

The output is `out/boston-housing-map.html`, one self-contained page. A first run downloads about 300 MB and takes 2–10 minutes; most of that is waiting on the public OpenStreetMap (Overpass) servers. The steps after the download take about 10 seconds.

## Pipeline

| Step | Script | What it does |
|---|---|---|
| fetch | `pipeline/fetch.py` | Downloads every source into `data/raw/` and skips files already there |
| base | `pipeline/base.py` | ZIP shapes within 26 km of the school, HUD and Zillow rents, MBTA lines and stations → `data/build/base.json` |
| commute | `pipeline/commute.py` | Weekday-morning minutes from every MBTA stop to the school, from the GTFS timetable (subway and bus) → `stop_minutes.json` |
| layers | `pipeline/layers.py` | Adds commute, crime, Census and amenity values per ZIP → `layers.json` |
| page | `build.py` | Puts `web/head.html`, `web/body.html` and `web/app.js` together with the data into the page |

Data years are set in `pipeline/config.py`. Change them there when a source publishes a new year: HUD in October, FBI in late summer, Census ACS in December.

## Sources

- HUD Small Area Fair Market Rents (rent by bedroom count, per ZIP)
- Zillow Observed Rent Index (typical asking rent, per ZIP)
- FBI Crime Data Explorer, *Crime in the United States*, Table 8 (offenses by city)
- Analyze Boston crime incident reports (used to split Boston's FBI total across its ZIPs)
- MBTA GTFS timetable and V3 API (commute times, lines, stations)
- US Census ACS 5-year summary files and the 2020 ZIP-to-town relationship file
- OpenStreetMap through Overpass (venues, cafés, groceries, parks) and the Bluebikes station feed

## Known limits

- Outside Boston, crime is a town-wide rate. Boston is split by ZIP using where the Boston Police logged each incident.
- ZIPs with fewer than 3,000 residents get no crime rate, because visitors swamp a per-resident figure.
- HUD rents sit near the 40th percentile of what recent movers paid. Zillow's asking rents can be far higher in the same ZIP; Dorchester is the clearest case.
- Commute times come from the timetable and leave out commuter rail.
