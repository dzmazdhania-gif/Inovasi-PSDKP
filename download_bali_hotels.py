import json
import requests
from datetime import datetime, timezone

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:180];

area["ISO3166-1"="ID"]["admin_level"="2"]->.country;
area["name"="Bali"]["boundary"="administrative"]->.bali;

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


def get_value(tags, key, default=""):
    return tags.get(key, default)


def element_to_feature(element):
    tags = element.get("tags", {})

    # Node
    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")

    # Way / Relation with center
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

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

    properties = {
        "osm_id": element.get("id"),
        "osm_type": element.get("type"),
        "name": get_value(tags, "name", "Unnamed"),
        "business_type": business_type,
        "tourism": tourism,
        "amenity": amenity,
        "leisure": leisure,
        "address": get_value(tags, "addr:street"),
        "village": get_value(tags, "addr:place"),
        "phone": get_value(tags, "phone"),
        "website": get_value(tags, "website"),
        "opening_hours": get_value(tags, "opening_hours"),
        "source": "OpenStreetMap",
    }

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": properties
    }


def main():
    print("Downloading Bali coastal business data...")
    print("Source: OpenStreetMap / Overpass API")

    response = requests.post(
        OVERPASS_URL,
        data=QUERY,
        timeout=240
    )

    response.raise_for_status()

    data = response.json()

    features = []

    for element in data.get("elements", []):
        feature = element_to_feature(element)

        if feature:
            features.append(feature)

    # Remove duplicate OSM objects
    unique_features = {}

    for feature in features:
        props = feature["properties"]
        key = f'{props["osm_type"]}_{props["osm_id"]}'
        unique_features[key] = feature

    features = list(unique_features.values())

    features.sort(
        key=lambda x: x["properties"]["name"].lower()
    )

    geojson = {
        "type": "FeatureCollection",
        "name": "Bali Coastal Businesses",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap / Overpass API",
        "features": features
    }

    output_file = "data/coastal_businesses.geojson"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            geojson,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("DONE")
    print(f"Total features: {len(features)}")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
