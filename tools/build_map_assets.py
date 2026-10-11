"""Regenerate the packaged map backgrounds in data/map/.

Both images share one EPSG:9498 kilometre frame (BBOX_KM); ambulance/bridge.py
ships that frame to the UI, which crops it to each case extent. Keep them in
sync if the frame ever changes.

Street map (data/map/caba-streets.webp): rendered here from the BBBike
OpenStreetMap extract for Buenos Aires
(https://download.bbbike.org/osm/bbbike/BuenosAires/BuenosAires.osm.shp.zip,
map data © OpenStreetMap contributors, ODbL). Needs pillow and pyshp:

    uv run --with pillow --with pyshp python tools/build_map_assets.py \\
        --osm-zip /tmp/caba-osm.shp.zip

Satellite image (data/map/caba-satellite.webp): a Sentinel-2 L2A true-colour
render of one low-cloud scene over the same frame, fetched through the
Microsoft Planetary Computer data API (contains modified Copernicus Sentinel
data; https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a). The API
returns WebP at the requested size; the packaged file may be re-compressed to
stay comfortably under Qollab's 2 MB file limit:

    python tools/build_map_assets.py --satellite
"""

import argparse
import sys
import urllib.request
from collections import Counter
from itertools import islice
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw

from tools.build_cases import to_9498

BBOX_KM = (11, 60, 33, 83)
SIZE = (1800, 1882)
SOURCE = "BuenosAires-shp/shape"
SATELLITE_ITEM = "S2A_MSIL2A_20240924T134711_R024_T21HUB_20240924T190249"
SATELLITE_URL = (
    "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/"
    "11000,60000,33000,83000/1800x1882.webp"
    "?collection=sentinel-2-l2a"
    f"&item={SATELLITE_ITEM}"
    "&assets=visual&coord_crs=EPSG:9498&dst_crs=EPSG:9498"
)


def reader(archive, name):
    import shapefile  # lazy: only needed for the OSM street render

    path = f"{SOURCE}/{name}"
    return shapefile.Reader(
        shp=BytesIO(archive.read(f"{path}.shp")),
        shx=BytesIO(archive.read(f"{path}.shx")),
        dbf=BytesIO(archive.read(f"{path}.dbf")),
    )


def screen(point):
    x, y = to_9498(*point)
    west, south, east, north = BBOX_KM
    return (
        (x / 1000 - west) * SIZE[0] / (east - west),
        (north - y / 1000) * SIZE[1] / (north - south),
    )


def visible(shape):
    if not shape.bbox:
        return False
    west, south, east, north = shape.bbox
    return east >= -58.6 and west <= -58.2 and north >= -34.76 and south <= -34.45


def paths(shape):
    points = shape.points
    ends = list(shape.parts) + [len(points)]
    for start, end in zip(ends, ends[1:]):
        if end > start:
            yield [screen(point) for point in points[start:end]]


def draw_shapes(draw, archive, name, colors, width=1):
    for feature in reader(archive, name).iterShapeRecords():
        shape = feature.shape
        if not visible(shape):
            continue
        kind = feature.record.as_dict().get("type")
        style = colors.get(kind)
        if not style:
            continue
        for points in paths(shape):
            if len(points) > 2 and shape.shapeType in (5, 15, 25):
                draw.polygon(points, fill=style)
            elif len(points) > 1:
                draw.line(points, fill=style[0] if isinstance(style, tuple) else style,
                          width=style[1] if isinstance(style, tuple) else width, joint="curve")


def build(archive, target):
    image = Image.new("RGB", SIZE, "#f2f1e9")
    draw = ImageDraw.Draw(image)
    draw_shapes(draw, archive, "landuse", {
        "forest": "#c5dcbd", "wood": "#c5dcbd", "park": "#d4e9cd",
        "recreation_groun": "#d4e9cd", "grass": "#deecd3",
        "cemetery": "#deead2", "nature_reserve": "#c5dcbd",
        "industrial": "#eae9e2", "commercial": "#ebe9e3",
    })
    draw_shapes(draw, archive, "natural", {
        "water": "#b8d7df", "park": "#d4e9cd", "forest": "#c5dcbd",
        "wood": "#c5dcbd", "scrub": "#dbe8ca",
        "wetland": "#c7e0dc", "beach": "#efdfbf",
    })
    draw_shapes(draw, archive, "waterways", {
        "river": ("#b8d7df", 7), "stream": ("#b8d7df", 3),
        "canal": ("#b8d7df", 3), "drain": ("#b8d7df", 2),
    })
    draw_shapes(draw, archive, "roads", {
        "residential": ("#ffffff", 2), "living_street": ("#ffffff", 2),
        "unclassified": ("#ffffff", 2), "service": ("#ffffff", 1),
        "pedestrian": ("#ffffff", 1), "track": ("#f3ebd9", 1),
        "tertiary": ("#f8f4e7", 3), "tertiary_link": ("#f8f4e7", 2),
        "secondary": ("#f3d6ab", 4), "secondary_link": ("#f3d6ab", 3),
        "primary": ("#efbe82", 5), "primary_link": ("#efbe82", 3),
        "trunk": ("#e3a56b", 6), "trunk_link": ("#e3a56b", 4),
        "motorway": ("#db9d67", 7), "motorway_link": ("#db9d67", 4),
    })
    image.save(target, "WEBP", quality=83, method=6)


def satellite(target):
    request = urllib.request.Request(
        SATELLITE_URL, headers={"User-Agent": "quantum-ambulance-assets"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    if Image.open(BytesIO(raw)).size != SIZE:
        raise ValueError("unexpected render size from the data API")
    with open(target, "wb") as output:
        output.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--osm-zip")
    parser.add_argument("--output", default="data/map/caba-streets.webp")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument(
        "--satellite",
        nargs="?",
        const="data/map/caba-satellite.webp",
        metavar="OUTPUT",
        help="download the Sentinel-2 background instead of rendering streets",
    )
    args = parser.parse_args()
    if args.satellite:
        satellite(args.satellite)
        return
    if not args.osm_zip:
        parser.error("--osm-zip is required to render the street map")
    with ZipFile(args.osm_zip) as archive:
        if args.inspect:
            for name in ("landuse", "natural", "waterways", "roads"):
                shape_reader = reader(archive, name)
                print(name, len(shape_reader), [field[0] for field in shape_reader.fields[1:]], shape_reader.shape(0).bbox, shape_reader.shape(0).points[:2])
                print([record.as_dict() for record in islice(shape_reader.iterRecords(), 3)])
                kinds = Counter(feature.record.as_dict().get("type") for feature in shape_reader.iterShapeRecords() if visible(feature.shape))
                print(kinds.most_common(30))
                if name == "natural":
                    waters = [feature.shape.bbox for feature in shape_reader.iterShapeRecords() if feature.record.as_dict().get("type") == "water" and visible(feature.shape)]
                    print(sorted(waters, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]), reverse=True)[:5])
        else:
            build(archive, args.output)


if __name__ == "__main__":
    main()
