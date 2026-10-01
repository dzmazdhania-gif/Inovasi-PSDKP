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

# Bounding box Bali
# south, west, north, east
BALI_BBOX = "-9.1,114.4,-8.0,115.8"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


# ============================================================
# OVERPASS QUERY
# ============================================================

QUERY = f"""
[out:json][timeout:300];

(
  /* =========================
     TOURISM
     ========================= */

  nwr["tourism"]["name"]({BALI_BBOX});

  /* =========================
     FOOD & DRINK
     ========================= */

  nwr["amenity"="restaurant"]["name"]({BALI_BBOX});
  nwr["amenity"="cafe"]["name"]({BALI_BBOX});
  nwr["amenity"="bar"]["name"]({BALI_BBOX});
  nwr["amenity"="pub"]["name"]({BALI_BBOX});
  nwr["amenity"="fast_food"]["name"]({BALI_BBOX});

  /* =========================
     MARINE / RECREATION
     ========================= */

  nwr["leisure"="marina"]["name"]({BALI_BBOX});
  nwr["leisure"="water_park"]["name"]({BALI_BBOX});
  nwr["leisure"="sports_centre"]["name"]({BALI_BBOX});

  /* =========================
     MARINE / DIVING / FISHING
     ========================= */

  nwr["shop"="diving"]["name"]({BALI_BBOX});
  nwr["shop"="fishing"]["name"]({BALI_BBOX});
  nwr["shop"="sports"]["name"]({BALI_BBOX});
  nwr["shop"="outdoor"]["name"]({BALI_BBOX});

  /* =========================
     OTHER COASTAL TOURISM
     ========================= */

  nwr["tourism"="attraction"]["name"]({BALI_BBOX});
  nwr["tourism"="hotel"]["name"]({BALI_BBOX});
  nwr["tourism"="resort"]["name"]({BALI_BBOX});
  nwr["tourism"="guest_house"]["name"]({BALI_BBOX});
  nwr["tourism"="hostel"]["name"]({BALI_BBOX});
  nwr["tourism"="motel"]["name"]({BALI_BBOX});
  nwr["tourism"="camp_site"]["name"]({BALI_BBOX});
  nwr["tourism"="chalet"]["name"]({BALI_BBOX});
  nwr["tourism"="apartment"]["name"]({BALI_BBOX});

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

        print()
        print("=" * 60)
        print("Trying Overpass endpoint:")
        print(endpoint)
        print("=" * 60)

        try:

            response = requests.post(
                endpoint,
                data={"data": QUERY},
                headers=headers,
                timeout=360
            )

            print("HTTP status:", response.status_code)

            if response.status_code == 200:

                data = response.json()

                elements = data.get(
                    "elements",
                    []
                )

                print(
                    "Downloaded OSM elements:",
                    len(elements)
                )

                if len(elements) > 0:
                    return data

                print(
                    "WARNING: Overpass returned 0 elements."
                )

            else:

                print("Overpass error:")
                print(response.text[:1000])

        except Exception as e:

            print(
                "Connection error:",
                repr(e)
            )

        time.sleep(3)

    raise RuntimeError(
        "All Overpass endpoints failed or returned no data."
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

    # Way / relation
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
        return tourism.replace(
            "_", " "
        ).title()

    if amenity:
        return amenity.replace(
            "_", " "
        ).title()

    if leisure:
        return leisure.replace(
            "_", " "
        ).title()

    if shop:
        return shop.replace(
            "_", " "
        ).title()

    return "Other"


# ============================================================
# DETERMINE MARINE RELEVANCE
# ============================================================

def determine_marine_relevance(tags):

    tourism = tags.get("tourism", "")
    amenity = tags.get("amenity", "")
    leisure = tags.get("leisure", "")
    shop = tags.get("shop", "")

    marine_types = {
        "marina",
        "diving",
        "fishing",
        "water_park",
        "beach",
        "attraction",
        "resort",
        "hotel"
    }

    values = {
        tourism,
        amenity,
        leisure,
        shop
    }

    if values.intersection(marine_types):

        return "Potentially marine/coastal"

    return "Coastal proximity"


# ============================================================
# CREATE RAW FEATURES
# ============================================================

def create_features(data):

    features = []

    for element in data.get(
        "elements",
        []
    ):

        tags = element.get(
            "tags",
            {}
        )

        name = tags.get(
            "name",
            ""
        ).strip()

        if not name:
            continue

        coordinates = get_coordinates(
            element
        )

        if not coordinates:
            continue

        lon, lat = coordinates

        try:

            lon = float(lon)
            lat = float(lat)

        except Exception:

            continue

        # Bali coordinate validation
        if not (
            -9.1 <= lat <= -8.0
        ):
            continue

        if not (
            114.4 <= lon <= 115.8
        ):
            continue

        business_type = (
            determine_business_type(tags)
        )

        marine_relevance = (
            determine_marine_relevance(tags)
        )

        properties = {

            "osm_id":
                element.get("id"),

            "osm_type":
                element.get("type"),

            "name":
                name,

            "business_type":
                business_type,

            "marine_relevance":
                marine_relevance,

            "tourism":
                tags.get("tourism", ""),

            "amenity":
                tags.get("amenity", ""),

            "leisure":
                tags.get("leisure", ""),

            "shop":
                tags.get("shop", ""),

            "address":
                tags.get("addr:full")
                or tags.get("addr:street")
                or "",

            "village":
                tags.get("addr:place")
                or tags.get("addr:village")
                or "",

            "phone":
                tags.get("phone")
                or tags.get("contact:phone")
                or "",

            "website":
                tags.get("website")
                or tags.get("contact:website")
                or "",

            "opening_hours":
                tags.get("opening_hours")
                or "",

            "source":
                "OpenStreetMap",

            "coastal_distance_m":
                None
        }

        feature = {

            "type":
                "Feature",

            "properties":
                properties,

            "geometry": {

                "type":
                    "Point",

                "coordinates":
                    [lon, lat]
            }
        }

        features.append(
            feature
        )

    return features


# ============================================================
# FILTER BY COASTLINE
# ============================================================

def filter_coastal_businesses(
    features
):

    print()
    print("=" * 60)
    print("Loading coastline:")
    print(COASTLINE_FILE)
    print("=" * 60)

    coastline = gpd.read_file(
        COASTLINE_FILE
    )

    if coastline.empty:

        raise RuntimeError(
            "coastline.geojson is empty."
        )

    if coastline.crs is None:

        print(
            "WARNING: coastline has no CRS."
        )

        coastline = coastline.set_crs(
            "EPSG:4326"
        )

    else:

        coastline = coastline.to_crs(
            "EPSG:4326"
        )

    coastline_geometry = unary_union(
        coastline.geometry
    )

    if not features:

        print(
            "WARNING: No business features."
        )

        return gpd.GeoDataFrame(
            geometry=[],
            crs="EPSG:4326"
        )

    gdf = gpd.GeoDataFrame(

        [
            feature["properties"]
            for feature in features
        ],

        geometry=[

            Point(
                feature[
                    "geometry"
                ]["coordinates"]
            )

            for feature in features
        ],

        crs="EPSG:4326"
    )

    print(
        "Raw businesses:",
        len(gdf)
    )

    # Bali = UTM Zone 50S
    gdf_projected = gdf.to_crs(
        "EPSG:32750"
    )

    coastline_projected = (
        gpd.GeoSeries(
            [coastline_geometry],
            crs="EPSG:4326"
        )
        .to_crs("EPSG:32750")
        .iloc[0]
    )

    # Calculate distance
    gdf_projected[
        "coastal_distance_m"
    ] = (

        gdf_projected.geometry
        .distance(
            coastline_projected
        )
    )

    # Filter <= 1 km
    coastal = gdf_projected[
        gdf_projected[
            "coastal_distance_m"
        ] <= MAX_DISTANCE_M
    ].copy()

    coastal[
        "coastal_distance_m"
    ] = coastal[
        "coastal_distance_m"
    ].round(1)

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

def remove_duplicates(
    gdf
):

    if gdf.empty:
        return gdf

    before = len(gdf)

    # OSM duplicate IDs
    gdf = gdf.drop_duplicates(
        subset=[
            "osm_type",
            "osm_id"
        ]
    )

    # Nearly identical locations
    gdf["_lon"] = (
        gdf.geometry.x.round(5)
    )

    gdf["_lat"] = (
        gdf.geometry.y.round(5)
    )

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

def export_geojson(
    gdf
):

    columns = [

        "osm_id",
        "osm_type",
        "name",
        "business_type",
        "marine_relevance",

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
    print(
        "Output:",
        OUTPUT_FILE
    )
    print(
        "Features:",
        len(gdf)
    )
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

    # 2. Convert OSM -> features
    features = create_features(
        data
    )

    print()
    print(
        "Named businesses extracted:",
        len(features)
    )

    if len(features) == 0:

        raise RuntimeError(
            "OSM returned data, but no named businesses "
            "were extracted."
        )

    # 3. Filter coastline
    coastal = (
        filter_coastal_businesses(
            features
        )
    )

    # 4. Remove duplicates
    coastal = (
        remove_duplicates(
            coastal
        )
    )

    # 5. Export
    export_geojson(
        coastal
    )


if __name__ == "__main__":

    main()
