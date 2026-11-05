"""
Garden Graph and Pathfinding Module.
Uses NetworkX to model walkways, intersections, and plant locations.
Implements Dijkstra & A* shortest path navigation and themed tour routing.
"""

import json
import math
import networkx as nx

class BotanicalGardenNavigator:
    def __init__(self, zones_json_path: str, plants_json_path: str):
        with open(zones_json_path, "r", encoding="utf-8") as f:
            self.zones_data = json.load(f)
        with open(plants_json_path, "r", encoding="utf-8") as f:
            self.plants_list = json.load(f)

        self.plants_by_id = {p["id"]: p for p in self.plants_list}
        self.plant_to_node = {}

        self.graph = nx.Graph()
        self._build_graph()

    def _build_graph(self):
        nodes_dict = self.zones_data["graph"]["nodes"]
        edges_list = self.zones_data["graph"]["edges"]

        # Add nodes with attributes
        for node_id, data in nodes_dict.items():
            self.graph.add_node(
                node_id,
                name=data.get("name", node_id),
                lat=data.get("lat"),
                lng=data.get("lng"),
                x=data.get("x"),
                y=data.get("y"),
                plant_id=data.get("plant_id")
            )
            if data.get("plant_id"):
                self.plant_to_node[data["plant_id"]] = node_id

        # Add edges with distance and path name
        for edge in edges_list:
            u = edge["from"]
            v = edge["to"]
            weight = edge.get("distance_meters", 50)
            path_name = edge.get("path_name", "Garden Path")
            self.graph.add_edge(u, v, weight=weight, path_name=path_name)

    def find_nearest_node(self, lat: float = None, lng: float = None, x: float = None, y: float = None) -> str:
        """Finds the closest graph node to a given GPS coordinate or map coordinate."""
        nodes = self.graph.nodes(data=True)
        best_node = "N_ENTRANCE"
        best_dist = float("inf")

        for node_id, data in nodes:
            if lat is not None and lng is not None and "lat" in data and "lng" in data:
                # Euclidean approximation for local garden scale
                d = (data["lat"] - lat)**2 + (data["lng"] - lng)**2
            elif x is not None and y is not None and "x" in data and "y" in data:
                d = (data["x"] - x)**2 + (data["y"] - y)**2
            else:
                continue

            if d < best_dist:
                best_dist = d
                best_node = node_id

        return best_node

    def navigate_to_plant(self, target_plant_id: str, start_node_id: str = "N_ENTRANCE", visitor_coords: dict = None):
        """
        Calculates shortest walking path from start location to target plant.
        Returns coordinates path, distance, walk time, and step-by-step instructions.
        """
        if visitor_coords and ("lat" in visitor_coords or "x" in visitor_coords):
            start_node_id = self.find_nearest_node(
                lat=visitor_coords.get("lat"),
                lng=visitor_coords.get("lng"),
                x=visitor_coords.get("x"),
                y=visitor_coords.get("y")
            )

        target_node = self.plant_to_node.get(target_plant_id)
        if not target_node:
            # Fallback search by node id
            target_node = f"P_{target_plant_id.upper()}"
            if target_node not in self.graph:
                raise ValueError(f"Plant ID '{target_plant_id}' has no corresponding map node.")

        try:
            path_nodes = nx.shortest_path(self.graph, source=start_node_id, target=target_node, weight="weight")
            total_distance = nx.shortest_path_length(self.graph, source=start_node_id, target=target_node, weight="weight")
        except nx.NetworkXNoPath:
            raise ValueError(f"No navigable path between {start_node_id} and {target_node}.")

        # Generate step-by-step directions and geometry points
        instructions = []
        path_coords_latlng = []
        path_coords_xy = []

        for i in range(len(path_nodes)):
            curr_node = path_nodes[i]
            node_data = self.graph.nodes[curr_node]
            path_coords_latlng.append([node_data["lat"], node_data["lng"]])
            path_coords_xy.append({"x": node_data["x"], "y": node_data["y"]})

            if i < len(path_nodes) - 1:
                next_node = path_nodes[i + 1]
                edge_data = self.graph.get_edge_data(curr_node, next_node)
                path_name = edge_data.get("path_name", "Path")
                step_dist = edge_data.get("weight", 0)

                step_text = f"Follow {path_name} towards {self.graph.nodes[next_node]['name']} ({step_dist}m)"
                instructions.append({
                    "step_number": i + 1,
                    "instruction": step_text,
                    "from_node": self.graph.nodes[curr_node]["name"],
                    "to_node": self.graph.nodes[next_node]["name"],
                    "distance_meters": step_dist
                })

        # Estimated walking time assuming comfortable 1.2 m/s pace (approx 72 m/min)
        walk_time_minutes = max(1, round(total_distance / 72.0))
        target_plant = self.plants_by_id.get(target_plant_id, {})

        return {
            "target_plant": {
                "id": target_plant_id,
                "common_name": target_plant.get("common_name", ""),
                "scientific_name": target_plant.get("scientific_name", ""),
                "zone_name": target_plant.get("zone_name", ""),
                "poi_near": target_plant.get("poi_near", "")
            },
            "start_node": self.graph.nodes[start_node_id]["name"],
            "total_distance_meters": int(total_distance),
            "estimated_minutes": walk_time_minutes,
            "path_nodes": path_nodes,
            "path_coords_latlng": path_coords_latlng,
            "path_coords_xy": path_coords_xy,
            "turn_instructions": instructions
        }

    def plan_themed_tour(self, tour_id: str):
        """
        Plans continuous walking itinerary visiting all stops in a themed tour.
        """
        tours = {t["id"]: t for t in self.zones_data["themed_tours"]}
        tour = tours.get(tour_id)
        if not tour:
            raise ValueError(f"Tour with ID '{tour_id}' not found.")

        current_node = "N_ENTRANCE"
        full_path_coords = []
        combined_instructions = []
        total_dist = 0

        for stop_idx, stop_node in enumerate(tour["stops"]):
            sub_path = nx.shortest_path(self.graph, source=current_node, target=stop_node, weight="weight")
            sub_dist = nx.shortest_path_length(self.graph, source=current_node, target=stop_node, weight="weight")
            total_dist += sub_dist

            for i in range(len(sub_path) - 1):
                u = sub_path[i]
                v = sub_path[i + 1]
                edge = self.graph.get_edge_data(u, v)
                u_data = self.graph.nodes[u]
                if not full_path_coords or full_path_coords[-1] != [u_data["lat"], u_data["lng"]]:
                    full_path_coords.append([u_data["lat"], u_data["lng"]])

            dest_data = self.graph.nodes[stop_node]
            full_path_coords.append([dest_data["lat"], dest_data["lng"]])

            combined_instructions.append({
                "stop_number": stop_idx + 1,
                "destination_name": dest_data["name"],
                "distance_from_prev": int(sub_dist)
            })
            current_node = stop_node

        return {
            "tour_info": tour,
            "total_distance_meters": int(total_dist),
            "estimated_minutes": max(1, round(total_dist / 65.0)),
            "path_coords_latlng": full_path_coords,
            "itinerary_stops": combined_instructions
        }
