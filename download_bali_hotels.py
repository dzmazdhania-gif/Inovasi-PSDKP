import json
import time
import requests
from datetime import datetime, timezone


# ============================================================
# OVERPASS API ENDPOINTS
# ============================================================

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


# ============================================================
# OVERPASS QUERY
# ============================================================

QUERY = """
[out:json][timeout:180];

area["name"="Bali"]["boundary"="administrative"]["admin_level"="4"]->.bali;

(
  nwr["tourism"="hotel"](area.bali);
  nwr["tourism"="resort"](area.bali);
  nwr["tourism"="guest_house"](area.bali);
  nwr["tourism"="hostel"](area.bali);
  nwr["tourism"="motel"](area.bali);

  nwr["amenity"="restaurant"](area.bali);
  nwr["amenity"="cafe"](area.bali);
  nwr["amenity"="bar"](area.bali);

  nwr["tourism"="attraction"](area.bali);
  nwr["tourism"="beach_resort"](area.bali);

  nwr["leisure"="beach_resort"](area.bali);
);

out center tags;
"""


# ============================================================
# HTTP SETTINGS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Marine-Check-Bali/1.0 "
        "(https://github.com/dzmazdhania-gif/Inovasi-PSDKP)"
    ),
    "Accept": "application/json",
}


# ============================================================
# GET VALUE FROM OSM TAGS
# ============================================================

def get_value(tags, key, default=""):
    return tags.get(key, default)


# ============================================================
# CONVERT OSM ELEMENT TO GEOJSON FEATURE
# ============================================================

def element_to_feature(element):

    tags = element.get("tags", {})

    # ----------------------------
    # NODE
    # ----------------------------

    if element["type"] == "node":

        lat = element.get("lat")
        lon = element.get("lon")

    # ----------------------------
    # WAY / RELATION
    # ----------------------------

    else:

        center = element.get("center", {})

        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    # ----------------------------
    # BUSINESS TYPE
    # ----------------------------

    tourism = get_value(tags, "tourism")
    amenity = get_value(tags, "amenity")
    leisure = get_value(tags, "leisure")

    if tourism:
        business_type = tourism

    elif amenity:
        business_type = amenity

    elif leisure:
        business_type = leisure

    else:
        business_type = "other"

    # ----------------------------
    # PROPERTIES
    # ----------------------------

    properties = {

        "osm_id":
            element.get("id"),

        "osm_type":
            element.get("type"),

        "name":
            get_value(
                tags,
                "name",
                "Unnamed"
            ),

        "business_type":
            business_type,

        "tourism":
            tourism,

        "amenity":
            amenity,

        "leisure":
            leisure,

        "address":
            get_value(
                tags,
                "addr:street"
            ),

        "village":
            get_value(
                tags,
                "addr:place"
            ),

        "phone":
            get_value(
                tags,
                "phone"
            ),

        "website":
            get_value(
                tags,
                "website"
            ),

        "opening_hours":
            get_value(
                tags,
                "opening_hours"
            ),

        "source":
            "OpenStreetMap",

    }

    # ----------------------------
    # GEOJSON
    # ----------------------------

    return {

        "type": "Feature",

        "geometry": {

            "type": "Point",

            "coordinates": [
                lon,
                lat
            ]

        },

        "properties":
            properties

    }


# ============================================================
# DOWNLOAD DATA
# ============================================================

def download_from_overpass():

    last_error = None

    for endpoint in OVERPASS_ENDPOINTS:

        print()
        print("----------------------------------------")
        print("Trying Overpass endpoint:")
        print(endpoint)
        print("----------------------------------------")

        try:

            response = requests.post(

                endpoint,

                data={
                    "data": QUERY
                },

                headers=HEADERS,

                timeout=240

            )

            print(
                "HTTP status:",
                response.status_code
            )

            response.raise_for_status()

            data = response.json()

            print(
                "Successfully downloaded data from:"
            )

            print(endpoint)

            return data

        except Exception as error:

            print(
                "Endpoint failed:"
            )

            print(error)

            last_error = error

            time.sleep(3)

    raise RuntimeError(
        "All Overpass API endpoints failed. "
        f"Last error: {last_error}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Downloading Bali coastal business data..."
    )

    print(
        "Source: OpenStreetMap / Overpass API"
    )

    # ----------------------------
    # DOWNLOAD
    # ----------------------------

    data = download_from_overpass()

    elements = data.get(
        "elements",
        []
    )

    print()
    print(
        "Raw OSM elements:",
        len(elements)
    )

    # ----------------------------
    # CONVERT TO GEOJSON
    # ----------------------------

    features = []

    for element in elements:

        feature = element_to_feature(
            element
        )

        if feature:

            features.append(
                feature
            )

    # ----------------------------
    # REMOVE DUPLICATES
    # ----------------------------

    unique_features = {}

    for feature in features:

        properties = feature[
            "properties"
        ]

        key = (
            f'{properties["osm_type"]}_'
            f'{properties["osm_id"]}'
        )

        unique_features[key] = feature

    features = list(
        unique_features.values()
    )

    # ----------------------------
    # SORT BY NAME
    # ----------------------------

    features.sort(

        key=lambda feature:
            feature["properties"]
            ["name"]
            .lower()

    )

    # ----------------------------
    # CREATE GEOJSON
    # ----------------------------

    geojson = {

        "type":
            "FeatureCollection",

        "name":
            "Bali Coastal Businesses",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source":
            "OpenStreetMap / Overpass API",

        "features":
            features

    }

    # ----------------------------
    # OUTPUT
    # ----------------------------

    output_file = (
        "coastal_businesses.geojson"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(

            geojson,

            file,

            ensure_ascii=False,

            indent=2

        )

    # ----------------------------
    # SUMMARY
    # ----------------------------

    print()
    print(
        "========================================"
    )

    print(
        "DONE"
    )

    print(
        "Total features:",
        len(features)
    )

    print(
        "Output file:",
        output_file
    )

    print(
        "========================================"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
