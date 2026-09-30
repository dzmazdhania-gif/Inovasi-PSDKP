import json
import time
import requests
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_FILE = "coastal_businesses.geojson"
COASTLINE_FILE = "coastline.geojson"

# Maksimum jarak usaha dari garis pantai
MAX_DISTANCE_M = 1000

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


# ============================================================
# OVERPASS QUERY
# ============================================================

QUERY = r"""
[out:json][timeout:180];

area["name"="Bali"]["boundary"="administrative"]["admin_level"="4"]->.bali;

(
  /*
   * TOURISM
   */
  nwr["tourism"]["name"](area.bali);

  /*
   * FOOD & DRINK
   */
  nwr["amenity"="restaurant"]["name"](area.bali);
  nwr["amenity"="cafe"]["name"](area.bali);
  nwr["amenity"="bar"]["name"](area.bali);
  nwr["amenity"="pub"]["name"](area.bali);
  nwr["amenity"="fast_food"]["name"](area.bali);

  /*
   * MARINE / RECREATIONAL ACTIVITIES
   */
  nwr["leisure"="marina"]["name"](area.bali);
  nwr["leisure"="water_park"]["name"](area.bali);
  nwr["leisure"="sports_centre"]["name"](area.bali);
  nwr["leisure"="resort"]["name"](area.bali);

  /*
   * SHOPS THAT MAY BE RELEVANT TO COASTAL TOURISM
   */
  nwr["shop"="sports"]["name"](area.bali);
  nwr["shop"="outdoor"]["name"](area.bali);
  nwr["shop"="fishing"]["name"](area.bali);
  nwr["shop"="diving"]["name"](area.bali);
  nwr["shop"="gift"]["name"](area.bali);
  nwr["shop"="souvenir"]["name"](area.bali);

  /*
   * BEACH / WATER TOURISM
   */
  nwr["tourism"="attraction"]["name"](area.bali);
  nwr["tourism"="hotel"]["name"](area.bali);
  nwr["tourism"="resort"]["name"](area.bali);
  nwr["tourism"="guest_house"]["name"](area.bali);
  nwr["tourism"="hostel"]["name"](area.bali);
  nwr["tourism"="motel"]["name"](area.bali);
  nwr["tourism"="camp_site"]["name"](area.bali);
  nwr["tourism"="chalet"]["name"](area.bali);
  nwr["tourism"="apartment"]["name"](area.bali);
  nwr["tourism"="alpine_hut"]["name"](area.bali);

);

out center tags;
"""


# ============================================================
# DOWNLOAD OSM DATA
# ============================================================

def download_osm_data():

    headers = {
        "User-Agent": "Marine-Check-Bali/1.0",
        "Accept": "application/json",
    }

    for endpoint in OVERPASS_ENDPOINTS:

        print(f"Trying Overpass endpoint:")
        print(endpoint)

        try:

            response = requests.post(
                endpoint,
                data={"data": QUERY},
                headers=headers,
                timeout=240
            )

            print("HTTP status:", response.status_code)

            if response.status_code == 200:

                data = response.json()

                print(
                    "Downloaded OSM elements:",
                    len(data.get("elements", []))
                )

                return data

            print("Overpass error:")
            print(response.text[:500])

        except Exception as e:

            print("Connection error:", e)

        time.sleep(2)

    raise RuntimeError(
        "All Overpass endpoints failed."
    )


# ============================================================
# GET COORDINATES
# ============================================================

def get_coordinates(element):

    # Node
    if "lat" in element and "lon" in element:

        return (
            element["lon"],
            element["lat"]
        )

    # Way / Relation with center
    if "center" in element:

        return (
            element["center"]["lon"],
            element["center"]["lat"]
        )

    return None


# ============================================================
# DETERMINE BUSINESS TYPE
# ============================================================

def determine_business_type(tags):

    tourism = tags.get("tourism", "")
    amenity = tags.get("amenity", "")
    leisure = tags.get("leisure", "")
    shop = tags.get("shop", "")

    if tourism:
        return tourism.replace("_", " ").title()

    if amenity:
        return amenity.replace("_", " ").title()

    if leisure:
        return leisure.replace("_", " ").title()

    if shop:
        return shop.replace("_", " ").title()

    return "Other"


# ============================================================
# CREATE RAW FEATURES
# ============================================================

def create_features(data):

    features = []

    for element in data.get("elements", []):

        tags = element.get("tags", {})

        name = tags.get("name", "").strip()

        if not name:
            continue

        coordinates = get_coordinates(element)

        if not coordinates:
            continue

        lon, lat = coordinates

        try:
            lon = float(lon)
            lat = float(lat)
        except Exception:
            continue

        # Basic coordinate validation
        if not (-9.5 <= lat <= -8.0):
            continue

        if not (114.0 <= lon <= 116.5):
            continue

        business_type = determine_business_type(tags)

        properties = {
            "osm_id": element.get("id"),
            "osm_type": element.get("type"),
            "name": name,
            "business_type": business_type,

            "tourism": tags.get("tourism"),
            "amenity": tags.get("amenity"),
            "leisure": tags.get("leisure"),
            "shop": tags.get("shop"),

            "address": tags.get("addr:full")
                       or tags.get("addr:street")
                       or "",

            "village": tags.get("addr:place")
                       or tags.get("addr:village")
                       or "",

            "phone": tags.get("phone")
                     or tags.get("contact:phone")
                     or "",

            "website": tags.get("website")
                       or tags.get("contact:website")
                       or "",

            "opening_hours": tags.get("opening_hours")
                             or "",

            "source": "OpenStreetMap",

            "coastal_distance_m": None
        }

        feature = {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        }

        features.append(feature)

    return features


# ============================================================
# FILTER BY COASTLINE
# ============================================================

def filter_coastal_businesses(features):

    print()
    print("Loading coastline:")
    print(COASTLINE_FILE)

    coastline = gpd.read_file(COASTLINE_FILE)

    if coastline.empty:
        raise RuntimeError(
            "coastline.geojson is empty."
        )

    # Make sure coastline has CRS
    if coastline.crs is None:
        print(
            "WARNING: coastline has no CRS."
            " Assuming EPSG:4326."
        )

        coastline = coastline.set_crs(
            "EPSG:4326"
        )

    else:
        coastline = coastline.to_crs(
            "EPSG:4326"
        )

    # Combine coastline geometries
    coastline_geometry = unary_union(
        coastline.geometry
    )

    # Convert businesses to GeoDataFrame
    gdf = gpd.GeoDataFrame(
        [
            feature["properties"]
            for feature in features
        ],
        geometry=[
            Point(
                feature["geometry"]["coordinates"]
            )
            for feature in features
        ],
        crs="EPSG:4326"
    )

    print(
        "Raw businesses:",
        len(gdf)
    )

    # Bali is in UTM Zone 50S
    # EPSG:32750 = WGS 84 / UTM zone 50S
    gdf_projected = gdf.to_crs(
        "EPSG:32750"
    )

    coastline_projected = gpd.GeoSeries(
        [coastline_geometry],
        crs="EPSG:4326"
    ).to_crs(
        "EPSG:32750"
    ).iloc[0]

    # Calculate distance to coastline
    gdf_projected[
        "coastal_distance_m"
    ] = gdf_projected.geometry.distance(
        coastline_projected
    )

    # Filter ≤ 1 km
    coastal = gdf_projected[
        gdf_projected[
            "coastal_distance_m"
        ] <= MAX_DISTANCE_M
    ].copy()

    # Round distance
    coastal[
        "coastal_distance_m"
    ] = coastal[
        "coastal_distance_m"
    ].round(1)

    # Back to WGS84
    coastal = coastal.to_crs(
        "EPSG:4326"
    )

    print(
        "Businesses within",
        MAX_DISTANCE_M,
        "m:",
        len(coastal)
    )

    return coastal


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(gdf):

    before = len(gdf)

    # First remove exact OSM duplicate IDs
    gdf = gdf.drop_duplicates(
        subset=["osm_type", "osm_id"]
    )

    # Then remove duplicate names at nearly identical
    # locations
    gdf["_lon"] = gdf.geometry.x.round(5)
    gdf["_lat"] = gdf.geometry.y.round(5)

    gdf = gdf.drop_duplicates(
        subset=[
            "name",
            "_lon",
            "_lat"
        ]
    )

    gdf = gdf.drop(
        columns=[
            "_lon",
            "_lat"
        ]
    )

    after = len(gdf)

    print(
        "Duplicates removed:",
        before - after
    )

    return gdf


# ============================================================
# EXPORT GEOJSON
# ============================================================

def export_geojson(gdf):

    # Keep only useful fields
    columns = [
        "osm_id",
        "osm_type",
        "name",
        "business_type",
        "tourism",
        "amenity",
        "leisure",
        "shop",
        "address",
        "village",
        "phone",
        "website",
        "opening_hours",
        "coastal_distance_m",
        "source",
        "geometry"
    ]

    existing_columns = [
        column
        for column in columns
        if column in gdf.columns
    ]

    gdf = gdf[
        existing_columns
    ]

    # Make sure GeoJSON is WGS84
    gdf = gdf.to_crs(
        "EPSG:4326"
    )

    gdf.to_file(
        OUTPUT_FILE,
        driver="GeoJSON"
    )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print("Output:", OUTPUT_FILE)
    print("Features:", len(gdf))
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("MARINE-CHECK BALI")
    print("Coastal Business Data Downloader")
    print("=" * 60)

    # 1. Download OSM
    data = download_osm_data()

    # 2. Convert OSM → features
    features = create_features(data)

    print(
        "Named businesses extracted:",
        len(features)
    )

    # 3. Filter by coastline
    coastal = filter_coastal_businesses(
        features
    )

    # 4. Remove duplicates
    coastal = remove_duplicates(
        coastal
    )

    # 5. Export
    export_geojson(
        coastal
    )


if __name__ == "__main__":
    main()
