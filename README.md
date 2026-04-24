This is a density-based heightmap from building data.

It's still in progress since the objects are not looking very nice once imported to Blender.

Usage Examples:
1. Download buildings from a place:
bash

python3 script.py --place "Stockholm, Sweden" --output stockholm_buildings --grid-size 300

2. Use an Overpass query file:

Create charging_stations.query:
xml

[out:json];
area["ISO3166-1"="SE"][admin_level=2];
node["amenity"="charging_station"](area);
out center;

Then run:
bash

python3 script.py --query-file charging_stations.query --output sweden_charging

3. Direct query:
bash

python3 script.py --query "[out:json]; area['ISO3166-1'='MZ']; node['railway'='station'](area); out center;" --output mozambique_railways --height-scale 15

4. Batch processing:

Create queries.txt:
text

Stockholm, Sweden
Gothenburg, Sweden
[out:json]; area["ISO3166-1"="DK"]; node["amenity"="cafe"](area); out center;
Berlin, Germany

Run:
bash

python3 script.py --batch queries.txt --output-dir my_exports

5. Interactive mode:
bash

python3 script.py --interactive

Install required packages:
bash

pip install osmnx geopandas numpy matplotlib requests

This script will create an output/ folder with:

    name.obj - 3D mesh file

    name.png - Heightmap texture

    name.mtl - Material file with texture reference

The OBJ files can be imported directly into Blender!


