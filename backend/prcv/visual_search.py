"""
Visual Plant Search (Content-Based Image Retrieval - CBIR).
Matches query images against garden database plant profiles using cosine similarity.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from backend.prcv.feature_extractor import extract_all_features

class VisualPlantSearchEngine:
    def __init__(self):
        self.plant_references = {} # plant_id -> normalized embedding
        self.is_indexed = False

    def index_reference_plants(self, plant_features_dict: dict):
        """
        Takes dictionary of plant_id -> embedding vectors or centroid vector
        and normalizes for cosine similarity.
        """
        self.plant_references = {}
        for plant_id, vec in plant_features_dict.items():
            arr = np.array(vec, dtype=np.float32)
            if len(arr.shape) > 1:
                arr = np.mean(arr, axis=0)
            norm = np.linalg.norm(arr)
            if norm > 1e-6:
                arr = arr / norm
            self.plant_references[plant_id] = arr
        self.is_indexed = True

    def search_by_image(self, query_image_bgr: np.ndarray, plants_db_dict: dict, deep_embedding: np.ndarray = None, top_k: int = 5):
        """
        Extracts features from query image and calculates cosine similarity
        against all indexed garden plant species.
        """
        if not self.is_indexed or not self.plant_references:
            raise RuntimeError("Visual search engine has not indexed reference plants yet.")

        query_res = extract_all_features(query_image_bgr)

        # Use deep embedding if provided and matching dimensionality
        ref_sample = next(iter(self.plant_references.values()))
        if deep_embedding is not None and len(deep_embedding) == len(ref_sample):
            q_vec = np.array(deep_embedding, dtype=np.float32)
        else:
            q_vec = query_res["vector"]

        q_norm = np.linalg.norm(q_vec)
        if q_norm > 1e-6:
            q_vec = q_vec / q_norm

        results = []
        for plant_id, ref_vec in self.plant_references.items():
            if len(q_vec) == len(ref_vec):
                sim = float(np.dot(q_vec, ref_vec))
            else:
                sim = 0.5

            match_score = round(max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0.9 else sim)) * 100, 1)
            plant_info = plants_db_dict.get(plant_id, {})
            results.append({
                "plant_id": plant_id,
                "common_name": plant_info.get("common_name", plant_id.capitalize()),
                "scientific_name": plant_info.get("scientific_name", ""),
                "zone_name": plant_info.get("zone_name", ""),
                "similarity_score": match_score,
                "dominant_colors": plant_info.get("color_profile", ""),
                "garden_coords": plant_info.get("garden_coords", {})
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {
            "query_features": query_res,
            "matches": results[:top_k]
        }
