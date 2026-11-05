"""
Botanical Database Repository.
Manages plants, zones, POIs, and queries.
"""

import json
import os

class BotanicalDatabase:
    def __init__(self, plants_path: str, zones_path: str):
        self.plants_path = plants_path
        self.zones_path = zones_path
        self.plants = []
        self.plants_map = {}
        self.zones_data = {}
        self.reload()

    def reload(self):
        with open(self.plants_path, "r", encoding="utf-8") as f:
            self.plants = json.load(f)
            self.plants_map = {p["id"]: p for p in self.plants}

        with open(self.zones_path, "r", encoding="utf-8") as f:
            self.zones_data = json.load(f)

    def get_all_plants(self):
        return self.plants

    def get_plant_by_id(self, plant_id: str):
        return self.plants_map.get(plant_id)

    def search_plants(self, query: str = "", zone_id: str = None):
        results = self.plants
        if zone_id and zone_id != "all":
            results = [p for p in results if p.get("zone_id") == zone_id]

        if query:
            q = query.lower().strip()
            results = [
                p for p in results
                if q in p["common_name"].lower()
                or q in p["scientific_name"].lower()
                or q in p["family"].lower()
                or q in p["description"].lower()
            ]
        return results

    def get_garden_zones(self):
        return self.zones_data.get("zones", [])

    def get_points_of_interest(self):
        return self.zones_data.get("points_of_interest", [])

    def get_themed_tours(self):
        return self.zones_data.get("themed_tours", [])

    def get_garden_metadata(self):
        return self.zones_data.get("garden_info", {})
