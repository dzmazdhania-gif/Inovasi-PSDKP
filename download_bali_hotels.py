import time
import math
import requests
import geopandas as gpd

from shapely.geometry import Point
from shapely.ops import unary_union


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_FILE = "coastal_businesses.geojson"
COASTLINE_FILE = "coastline.geojson"

# Maksimal jarak dari garis pantai
MAX_DISTANCE_M = 1000

# Bali bounding box
# south, west, north, east
BALI_BBOX = "-9.1,114.4,-8.0,115.8"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

MAX_RETRIES_PER_QUERY = 3
RETRY_DELAY_SECONDS = 8


# ============================================================
# USER AGENT
# ============================================================

HEADERS = {
    "User-Agent": (
        "Marine-Check-Bali/1.0 "
        "(https://github.com/dzmazdhania-gif/Inovasi-PSDKP)"
    ),
    "Accept": "application/json",
}


# ============================================================
# OVERPASS QUERY
# ============================================================

QUERY = f"""
[out:json][timeout:300];

(
    /*
    ============================================================
    ACCOMMODATION
    ============================================================
    */

    nwr["tourism"="hotel"]["name"]({BALI_BBOX});
    nwr["tourism"="resort"]["name"]({BALI_BBOX});
    nwr["tourism"="guest_house"]["name"]({BALI_BBOX});
    nwr["tourism"="hostel"]["name"]({BALI_BBOX});
    nwr["tourism"="motel"]["name"]({BALI_BBOX});
    nwr["tourism"="apartment"]["name"]({BALI_BBOX});
    nwr["tourism"="chalet"]["name"]({BALI_BBOX});
    nwr["tourism"="camp_site"]["name"]({BALI_BBOX});

    /*
    ============================================================
    MARINE TOURISM
    ============================================================
    */

    nwr["tourism"="attraction"]["name"]({BALI_BBOX});
    nwr["tourism"="viewpoint"]["name"]({BALI_BBOX});
    nwr["tourism"="theme_park"]["name"]({BALI_BBOX});

    /*
    ============================================================
    MARINA / WATER ACTIVITIES
    ============================================================
    */

    nwr["leisure"="marina"]["name"]({BALI_BBOX});
    nwr["leisure"="slipway"]["name"]({BALI_BBOX});
    nwr["leisure"="water_park"]["name"]({BALI_BBOX});
    nwr["leisure"="sports_centre"]["name"]({BALI_BBOX});
    nwr["leisure"="beach_resort"]["name"]({BALI_BBOX});

    /*
    ============================================================
    DIVING / SURFING / SAILING / FISHING
    ============================================================
    */

    nwr["sport"="diving"]["name"]({BALI_BBOX});
    nwr["sport"="surfing"]["name"]({BALI_BBOX});
    nwr["sport"="sailing"]["name"]({BALI_BBOX});
    nwr["sport"="fishing"]["name"]({BALI_BBOX});
    nwr["sport"="swimming"]["name"]({BALI_BBOX});
    nwr["sport"="kitesurfing"]["name"]({BALI_BBOX});
    nwr["sport"="windsurfing"]["name"]({BALI_BBOX});

    /*
    ============================================================
    MARINE / OUTDOOR SHOPS
    ============================================================
    */

    nwr["shop"="diving"]["name"]({BALI_BBOX});
    nwr["shop"="fishing"]["name"]({BALI_BBOX});
    nwr["shop"="sports"]["name"]({BALI_BBOX});
    nwr["shop"="outdoor"]["name"]({BALI_BBOX});
    nwr["shop"="boat"]["name"]({BALI_BBOX});

    /*
    ============================================================
    BOAT / WATER RENTAL
    ============================================================
    */

    nwr["amenity"="boat_rental"]["name"]({BALI_BBOX});
    nwr["amenity"="boat_storage"]["name"]({BALI_BBOX});

    /*
    ============================================================
    COASTAL FOOD / HOSPITALITY
    ============================================================
    */

    nwr["amenity"="restaurant"]["name"]({BALI_BBOX});
    nwr["amenity"="cafe"]["name"]({BALI_BBOX});
    nwr["amenity"="bar"]["name"]({BALI_BBOX});
    nwr["amenity"="pub"]["name"]({BALI_BBOX});

    /*
    ============================================================
    BEACH / RECREATION
    ============================================================
    */

    nwr["leisure"="beach"]["name"]({BALI_BBOX});
    nwr["leisure"="golf_course"]["name"]({BALI_BBOX});
);

out center tags;
"""


# ============================================================
# DOWNLOAD OSM
# ============================================================

def download_osm_data():

    print()
    print("=" * 70)
    print("DOWNLOADING OSM DATA")
    print("=" * 70)

    for attempt in range(1, MAX_RETRIES_PER_QUERY + 1):

        print()
        print(f"Attempt {attempt}/{MAX_RETRIES_PER_QUERY}")

        for endpoint in OVERPASS_ENDPOINTS:

            print()
            print("Trying:", endpoint)

            try:

                response = requests.post(
                    endpoint,
                    data={"data": QUERY},
                    headers=HEADERS,
                    timeout=360
                )

                print(
                    "HTTP status:",
                    response.status_code
                )

                if response.status_code != 200:

                    print(
                        response.text[:500]
                    )

                    continue

                data = response.json()

                elements = data.get(
                    "elements",
                    []
                )

                print(
                    "Downloaded elements:",
                    len(elements)
                )

                if elements:

                    return data

            except Exception as error:

                print(
                    "Connection error:",
                    repr(error)
                )

            time.sleep(3)

        if attempt < MAX_RETRIES_PER_QUERY:

            print()
            print(
                f"Waiting {RETRY_DELAY_SECONDS} seconds..."
            )

            time.sleep(
                RETRY_DELAY_SECONDS
            )

    raise RuntimeError(
        "All Overpass servers failed."
    )


# ============================================================
# COORDINATES
# ============================================================

def get_coordinates(element):

    # Node
    if "lat" in element and "lon" in element:

        return (
            float(element["lon"]),
            float(element["lat"])
        )

    # Way / relation
    if "center" in element:

        center = element["center"]

        if "lat" in center and "lon" in center:

            return (
                float(center["lon"]),
                float(center["lat"])
            )

    return None


# ============================================================
# BUSINESS TYPE
# ============================================================

def determine_business_type(tags):

    priority = [
        "sport",
        "shop",
        "leisure",
        "tourism",
        "amenity"
    ]

    for key in priority:

        value = tags.get(key, "")

        if value:

            return value.replace(
                "_",
                " "
            ).title()

    return "Other"


# ============================================================
# MARINE RELEVANCE
# ============================================================

def determine_marine_relevance(tags):

    marine_values = {

        "diving",
        "surfing",
        "sailing",
        "fishing",
        "swimming",
        "kitesurfing",
        "windsurfing",
        "marina",
        "slipway",
        "boat_rental",
        "boat_storage",
        "beach_resort",
        "water_park"
    }

    values = {

        tags.get("sport", ""),
        tags.get("shop", ""),
        tags.get("leisure", ""),
        tags.get("amenity", ""),
        tags.get("tourism", "")
    }

    if values.intersection(
        marine_values
    ):

        return "Marine-related"

    return "Coastal proximity"


# ============================================================
# CREATE FEATURES
# ============================================================

def create_features(data):

    features = []

    elements = data.get(
        "elements",
        []
    )

    print()
    print(
        "Processing OSM elements:",
        len(elements)
    )

    for element in elements:

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

        # Bali validation
        if not (
            114.4 <= lon <= 115.8
            and
            -9.1 <= lat <= -8.0
        ):

            continue

        feature = {

            "type": "Feature",

            "properties": {

                "osm_id":
                    element.get("id"),

                "osm_type":
                    element.get("type"),

                "name":
                    name,

                "business_type":
                    determine_business_type(
                        tags
                    ),

                "marine_relevance":
                    determine_marine_relevance(
                        tags
                    ),

                "tourism":
                    tags.get(
                        "tourism",
                        ""
                    ),

                "amenity":
                    tags.get(
                        "amenity",
                        ""
                    ),

                "leisure":
                    tags.get(
                        "leisure",
                        ""
                    ),

                "shop":
                    tags.get(
                        "shop",
                        ""
                    ),

                "sport":
                    tags.get(
                        "sport",
                        ""
                    ),

                "address":
                    (
                        tags.get("addr:full")
                        or
                        tags.get("addr:street")
                        or
                        ""
                    ),

                "village":
                    (
                        tags.get("addr:place")
                        or
                        tags.get("addr:village")
                        or
                        ""
                    ),

                "phone":
                    (
                        tags.get("phone")
                        or
                        tags.get("contact:phone")
                        or
                        ""
                    ),

                "website":
                    (
                        tags.get("website")
                        or
                        tags.get("contact:website")
                        or
                        ""
                    ),

                "opening_hours":
                    tags.get(
                        "opening_hours",
                        ""
                    ),

                "source":
                    "OpenStreetMap",

                "coastal_distance_m":
                    None
            },

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

    print()
    print(
        "Named OSM businesses:",
        len(features)
    )

    return features


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_distance(
    lon1,
    lat1,
    lon2,
    lat2
):

    R = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(
        lat2 - lat1
    )

    dlambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dphi / 2) ** 2
        +
        math.cos(phi1)
        *
        math.cos(phi2)
        *
        math.sin(dlambda / 2) ** 2
    )

    return (
        2
        *
        R
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )
    )


# ============================================================
# FILTER COASTAL BUSINESSES
# ============================================================

def filter_coastal_businesses(
    features
):

    print()
    print("=" * 70)
    print("FILTERING COASTAL BUSINESSES")
    print("=" * 70)

    coastline = gpd.read_file(
        COASTLINE_FILE
    )

    if coastline.empty:

        raise RuntimeError(
            "coastline.geojson is empty."
        )

    if coastline.crs is None:

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

    # --------------------------------------------------------
    # IMPORTANT:
    # use local UTM zones automatically
    # --------------------------------------------------------

    results = []

    print(
        "Input businesses:",
        len(features)
    )

    for feature in features:

        lon, lat = feature[
            "geometry"
        ]["coordinates"]

        point = Point(
            lon,
            lat
        )

        # Bali:
        # west -> UTM 50S
        # east -> UTM 51S
        epsg = (
            32750
            if lon < 114.0
            else 32751
        )

        point_gdf = gpd.GeoSeries(
            [point],
            crs="EPSG:4326"
        ).to_crs(
            f"EPSG:{epsg}"
        )

        coast_gdf = gpd.GeoSeries(
            [coastline_geometry],
            crs="EPSG:4326"
        ).to_crs(
            f"EPSG:{epsg}"
        )

        distance = point_gdf.iloc[0].distance(
            coast_gdf.iloc[0]
        )

        if distance <= MAX_DISTANCE_M:

            new_feature = feature.copy()

            new_feature[
                "properties"
            ] = feature[
                "properties"
            ].copy()

            new_feature[
                "properties"
            ][
                "coastal_distance_m"
            ] = round(
                distance,
                1
            )

            results.append(
                new_feature
            )

    print()
    print(
        "Businesses within",
        MAX_DISTANCE_M,
        "m:",
        len(results)
    )

    return results


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(
    features
):

    print()
    print(
        "Removing duplicates..."
    )

    seen = set()
    unique = []

    for feature in features:

        props = feature[
            "properties"
        ]

        osm_key = (
            props.get("osm_type"),
            props.get("osm_id")
        )

        if osm_key in seen:

            continue

        seen.add(
            osm_key
        )

        unique.append(
            feature
        )

    print(
        "Before:",
        len(features)
    )

    print(
        "After:",
        len(unique)
    )

    print(
        "Duplicates removed:",
        len(features) - len(unique)
    )

    return unique


# ============================================================
# EXPORT
# ============================================================

def export_geojson(
    features
):

    print()
    print(
        "Exporting GeoJSON..."
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

    gdf.to_file(
        OUTPUT_FILE,
        driver="GeoJSON"
    )

    print()
    print("=" * 70)
    print("SUCCESS")
    print("=" * 70)

    print(
        "Output:",
        OUTPUT_FILE
    )

    print(
        "Features:",
        len(gdf)
    )

    print(
        "Maximum coastline distance:",
        MAX_DISTANCE_M,
        "meters"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("MARINE-CHECK BALI")
    print("Coastal Business Data Downloader")
    print("=" * 70)

    # 1. Download OSM
    data = download_osm_data()

    # 2. OSM -> features
    features = create_features(
        data
    )

    if not features:

        raise RuntimeError(
            "No named businesses extracted."
        )

    # 3. Coastal filter
    coastal = filter_coastal_businesses(
        features
    )

    if not coastal:

        raise RuntimeError(
            "No businesses within coastline distance."
        )

    # 4. Remove duplicates
    coastal = remove_duplicates(
        coastal
    )

    # 5. Export
    export_geojson(
        coastal
    )

    print()
    print(
        "Marine-Check Bali data update completed."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
