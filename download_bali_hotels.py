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

# Usaha maksimal 1 km dari garis pantai
MAX_DISTANCE_M = 1000

# Bounding box Bali
# south, west, north, east
BALI_BBOX = "-9.1,114.4,-8.0,115.8"

# Overpass servers
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Retry
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
# OVERPASS QUERY BATCHES
# ============================================================

QUERY_BATCHES = [

    # --------------------------------------------------------
    # BATCH 1 — HOTELS / RESORTS / ACCOMMODATION
    # --------------------------------------------------------

    f"""
    [out:json][timeout:120];

    (
        nwr["tourism"="hotel"]["name"]({BALI_BBOX});
        nwr["tourism"="resort"]["name"]({BALI_BBOX});
        nwr["tourism"="guest_house"]["name"]({BALI_BBOX});
        nwr["tourism"="hostel"]["name"]({BALI_BBOX});
        nwr["tourism"="motel"]["name"]({BALI_BBOX});
        nwr["tourism"="apartment"]["name"]({BALI_BBOX});
        nwr["tourism"="chalet"]["name"]({BALI_BBOX});
        nwr["tourism"="camp_site"]["name"]({BALI_BBOX});
    );

    out center tags;
    """,

    # --------------------------------------------------------
    # BATCH 2 — RESTAURANT / CAFE / BAR
    # --------------------------------------------------------

    f"""
    [out:json][timeout:120];

    (
        nwr["amenity"="restaurant"]["name"]({BALI_BBOX});
        nwr["amenity"="cafe"]["name"]({BALI_BBOX});
        nwr["amenity"="bar"]["name"]({BALI_BBOX});
        nwr["amenity"="pub"]["name"]({BALI_BBOX});
        nwr["amenity"="fast_food"]["name"]({BALI_BBOX});
    );

    out center tags;
    """,

    # --------------------------------------------------------
    # BATCH 3 — MARINE / DIVING / FISHING
    # --------------------------------------------------------

    f"""
    [out:json][timeout:120];

    (
        nwr["leisure"="marina"]["name"]({BALI_BBOX});
        nwr["leisure"="water_park"]["name"]({BALI_BBOX});
        nwr["leisure"="sports_centre"]["name"]({BALI_BBOX});

        nwr["shop"="diving"]["name"]({BALI_BBOX});
        nwr["shop"="fishing"]["name"]({BALI_BBOX});
        nwr["shop"="sports"]["name"]({BALI_BBOX});
        nwr["shop"="outdoor"]["name"]({BALI_BBOX});
    );

    out center tags;
    """,

    # --------------------------------------------------------
    # BATCH 4 — TOURISM / ATTRACTIONS
    # --------------------------------------------------------

    f"""
    [out:json][timeout:120];

    (
        nwr["tourism"="attraction"]["name"]({BALI_BBOX});
        nwr["tourism"="theme_park"]["name"]({BALI_BBOX});
        nwr["tourism"="museum"]["name"]({BALI_BBOX});
        nwr["tourism"="viewpoint"]["name"]({BALI_BBOX});
    );

    out center tags;
    """,

    # --------------------------------------------------------
    # BATCH 5 — OTHER COASTAL RECREATION
    # --------------------------------------------------------

    f"""
    [out:json][timeout:120];

    (
        nwr["leisure"="beach_resort"]["name"]({BALI_BBOX});
        nwr["leisure"="golf_course"]["name"]({BALI_BBOX});
        nwr["sport"="surfing"]["name"]({BALI_BBOX});
        nwr["sport"="diving"]["name"]({BALI_BBOX});
        nwr["sport"="sailing"]["name"]({BALI_BBOX});
    );

    out center tags;
    """
]


# ============================================================
# DOWNLOAD ONE OVERPASS QUERY
# ============================================================

def download_query(query, batch_number):

    print()
    print("=" * 70)
    print(f"OVERPASS BATCH {batch_number}")
    print("=" * 70)

    endpoint_order = list(OVERPASS_ENDPOINTS)

    for attempt in range(MAX_RETRIES_PER_QUERY):

        print()
        print(
            f"Attempt {attempt + 1}/"
            f"{MAX_RETRIES_PER_QUERY}"
        )

        for endpoint in endpoint_order:

            print()
            print("Trying:")
            print(endpoint)

            try:

                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=180
                )

                print(
                    "HTTP status:",
                    response.status_code
                )

                if response.status_code == 200:

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

                    print(
                        "WARNING: Server returned "
                        "zero elements."
                    )

                else:

                    print(
                        "Server response:",
                        response.text[:500]
                    )

            except Exception as error:

                print(
                    "Connection error:",
                    repr(error)
                )

            time.sleep(3)

        print()
        print(
            "All endpoints failed for this attempt."
        )

        if attempt < MAX_RETRIES_PER_QUERY - 1:

            print(
                f"Waiting {RETRY_DELAY_SECONDS} seconds..."
            )

            time.sleep(
                RETRY_DELAY_SECONDS
            )

    print()
    print(
        f"WARNING: Batch {batch_number} failed."
    )

    return {
        "elements": []
    }


# ============================================================
# DOWNLOAD ALL BATCHES
# ============================================================

def download_osm_data():

    all_elements = []

    for index, query in enumerate(
        QUERY_BATCHES,
        start=1
    ):

        data = download_query(
            query,
            index
        )

        elements = data.get(
            "elements",
            []
        )

        all_elements.extend(
            elements
        )

        print()
        print(
            f"Batch {index} contributed:",
            len(elements),
            "elements"
        )

        # Give Overpass a short break
        time.sleep(5)

    print()
    print("=" * 70)
    print("OVERPASS DOWNLOAD COMPLETE")
    print("=" * 70)

    print(
        "Total raw elements:",
        len(all_elements)
    )

    return {
        "elements": all_elements
    }


# ============================================================
# GET COORDINATES
# ============================================================

def get_coordinates(element):

    # Node
    if (
        "lat" in element
        and "lon" in element
    ):

        return (
            element["lon"],
            element["lat"]
        )

    # Way / Relation
    if "center" in element:

        center = element["center"]

        if (
            "lat" in center
            and "lon" in center
        ):

            return (
                center["lon"],
                center["lat"]
            )

    return None


# ============================================================
# BUSINESS TYPE
# ============================================================

def determine_business_type(tags):

    tourism = tags.get(
        "tourism",
        ""
    )

    amenity = tags.get(
        "amenity",
        ""
    )

    leisure = tags.get(
        "leisure",
        ""
    )

    shop = tags.get(
        "shop",
        ""
    )

    sport = tags.get(
        "sport",
        ""
    )

    if tourism:

        return tourism.replace(
            "_",
            " "
        ).title()

    if amenity:

        return amenity.replace(
            "_",
            " "
        ).title()

    if leisure:

        return leisure.replace(
            "_",
            " "
        ).title()

    if shop:

        return shop.replace(
            "_",
            " "
        ).title()

    if sport:

        return sport.replace(
            "_",
            " "
        ).title()

    return "Other"


# ============================================================
# MARINE RELEVANCE
# ============================================================

def determine_marine_relevance(tags):

    values = {

        tags.get("tourism", ""),
        tags.get("amenity", ""),
        tags.get("leisure", ""),
        tags.get("shop", ""),
        tags.get("sport", "")
    }

    marine_types = {

        "marina",
        "diving",
        "fishing",
        "water_park",
        "beach_resort",
        "surfing",
        "sailing"
    }

    if values.intersection(
        marine_types
    ):

        return "Marine-related"

    return "Coastal proximity"


# ============================================================
# CREATE FEATURES
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

        try:

            lon = float(
                coordinates[0]
            )

            lat = float(
                coordinates[1]
            )

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
            determine_business_type(
                tags
            )
        )

        marine_relevance = (
            determine_marine_relevance(
                tags
            )
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
                    or tags.get("addr:street")
                    or ""
                ),

            "village":
                (
                    tags.get("addr:place")
                    or tags.get("addr:village")
                    or ""
                ),

            "phone":
                (
                    tags.get("phone")
                    or tags.get("contact:phone")
                    or ""
                ),

            "website":
                (
                    tags.get("website")
                    or tags.get("contact:website")
                    or ""
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

    print()
    print(
        "Named businesses extracted:",
        len(features)
    )

    return features


# ============================================================
# FILTER BY COASTLINE
# ============================================================

def filter_coastal_businesses(
    features
):

    print()
    print("=" * 70)
    print("LOADING COASTLINE")
    print("=" * 70)

    coastline = gpd.read_file(
        COASTLINE_FILE
    )

    if coastline.empty:

        raise RuntimeError(
            "coastline.geojson is empty."
        )

    print(
        "Coastline features:",
        len(coastline)
    )

    # Ensure CRS
    if coastline.crs is None:

        print(
            "WARNING: coastline has no CRS."
        )

        print(
            "Assuming EPSG:4326."
        )

        coastline = coastline.set_crs(
            "EPSG:4326"
        )

    else:

        coastline = coastline.to_crs(
            "EPSG:4326"
        )

    # Merge coastline
    coastline_geometry = unary_union(
        coastline.geometry
    )

    if not features:

        raise RuntimeError(
            "No named business features "
            "were extracted from OSM."
        )

    # Business GeoDataFrame
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

    # --------------------------------------------------------
    # PROJECT TO UTM 50S
    # --------------------------------------------------------

    print(
        "Projecting to EPSG:32750..."
    )

    gdf_projected = gdf.to_crs(
        "EPSG:32750"
    )

    coastline_projected = (

        gpd.GeoSeries(
            [coastline_geometry],
            crs="EPSG:4326"
        )

        .to_crs(
            "EPSG:32750"
        )

        .iloc[0]
    )

    # --------------------------------------------------------
    # DISTANCE TO COASTLINE
    # --------------------------------------------------------

    print(
        "Calculating distance to coastline..."
    )

    gdf_projected[
        "coastal_distance_m"
    ] = (

        gdf_projected.geometry
        .distance(
            coastline_projected
        )
    )

    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    coastal = gdf_projected[
        gdf_projected[
            "coastal_distance_m"
        ]
        <= MAX_DISTANCE_M
    ].copy()

    coastal[
        "coastal_distance_m"
    ] = (

        coastal[
            "coastal_distance_m"
        ]

        .round(1)
    )

    print()
    print(
        "Businesses within",
        MAX_DISTANCE_M,
        "meters:",
        len(coastal)
    )

    # Back to WGS84
    coastal = coastal.to_crs(
        "EPSG:4326"
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

    print()
    print(
        "Removing duplicates..."
    )

    before = len(gdf)

    # OSM ID duplicates
    gdf = gdf.drop_duplicates(
        subset=[
            "osm_type",
            "osm_id"
        ]
    )

    # Duplicate names at almost
    # identical coordinates
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
        "Before:",
        before
    )

    print(
        "After:",
        after
    )

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

    print()
    print(
        "Exporting GeoJSON..."
    )

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
        "sport",

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

    # WGS84 / GeoJSON
    gdf = gdf.to_crs(
        "EPSG:4326"
    )

    # Export
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

    # --------------------------------------------------------
    # 1. DOWNLOAD OSM
    # --------------------------------------------------------

    data = download_osm_data()

    raw_elements = data.get(
        "elements",
        []
    )

    print()
    print(
        "Total downloaded OSM elements:",
        len(raw_elements)
    )

    if not raw_elements:

        raise RuntimeError(
            "No OSM data was downloaded."
        )

    # --------------------------------------------------------
    # 2. OSM -> FEATURES
    # --------------------------------------------------------

    features = create_features(
        data
    )

    if not features:

        raise RuntimeError(
            "OSM data was downloaded, "
            "but no named businesses were extracted."
        )

    # --------------------------------------------------------
    # 3. COASTAL FILTER
    # --------------------------------------------------------

    coastal = (
        filter_coastal_businesses(
            features
        )
    )

    # --------------------------------------------------------
    # 4. REMOVE DUPLICATES
    # --------------------------------------------------------

    coastal = (
        remove_duplicates(
            coastal
        )
    )

    if coastal.empty:

        raise RuntimeError(
            "No businesses were found "
            "within the coastline distance."
        )

    # --------------------------------------------------------
    # 5. EXPORT
    # --------------------------------------------------------

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
