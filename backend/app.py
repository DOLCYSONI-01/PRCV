"""
FastAPI Main Application for AI Botanical Garden Navigator.
Serves REST APIs for plant identification, garden mapping, graph navigation,
visual plant search, and PRCV academic evaluation.
"""

import os
import io
import json
import base64
import cv2
import numpy as np
import joblib
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.database import BotanicalDatabase
from backend.garden_graph import BotanicalGardenNavigator
from backend.prcv.preprocessor import preprocess_image, generate_pipeline_visuals
from backend.prcv.feature_extractor import extract_all_features
from backend.prcv.classical_models import BotanicalClassicalClassifier
from backend.prcv.cnn_model import BotanicalCNNClassifier
from backend.prcv.visual_search import VisualPlantSearchEngine

app = FastAPI(
    title="AI Botanical Garden Navigator",
    description="PRCV-powered plant identification, interactive garden mapping, and smart navigation",
    version="1.0.0"
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

db = BotanicalDatabase(
    plants_path=os.path.join(DATA_DIR, "plants.json"),
    zones_path=os.path.join(DATA_DIR, "garden_zones.json")
)

navigator = BotanicalGardenNavigator(
    zones_json_path=os.path.join(DATA_DIR, "garden_zones.json"),
    plants_json_path=os.path.join(DATA_DIR, "plants.json")
)

classical_classifier = BotanicalClassicalClassifier()
cnn_classifier = BotanicalCNNClassifier()
visual_search_engine = VisualPlantSearchEngine()
eval_metrics_data = {}

def load_ai_models():
    """Load trained PRCV models if available."""
    global eval_metrics_data
    try:
        if os.path.exists(os.path.join(MODELS_DIR, "cnn_model.keras")):
            cnn_classifier.load(MODELS_DIR)
            print("Loaded MobileNetV2 Transfer Learning CNN")
        if os.path.exists(os.path.join(MODELS_DIR, "svm_model.joblib")):
            classical_classifier.load(MODELS_DIR)
            print("Loaded Classical Models (SVM, KNN, RF)")
        if os.path.exists(os.path.join(MODELS_DIR, "plant_references.joblib")):
            refs = joblib.load(os.path.join(MODELS_DIR, "plant_references.joblib"))
            visual_search_engine.index_reference_plants(refs)
            print("Indexed Visual Search Embeddings")
        metrics_file = os.path.join(MODELS_DIR, "prcv_evaluation_metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                eval_metrics_data = json.load(f)
            print("Loaded Academic PRCV Metrics")
    except Exception as e:
        print(f"Notice during model loading: {e}")

@app.on_event("startup")
def startup_event():
    load_ai_models()

def parse_input_image(file: UploadFile = None, image_base64: str = None) -> np.ndarray:
    """Decodes uploaded file or base64 data string to OpenCV BGR numpy array."""
    if file is not None and file.filename:
        contents = file.file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return img

    if image_base64:
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        decoded = base64.b64decode(image_base64)
        nparr = np.frombuffer(decoded, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return img

    raise HTTPException(status_code=400, detail="No valid image provided via file upload or base64.")

# ----------------- REST ENDPOINTS -----------------

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/api/plants")
def get_plants(q: str = Query("", description="Search term"), zone_id: str = Query("all", description="Filter by zone")):
    return db.search_plants(query=q, zone_id=zone_id)

@app.get("/api/plants/{plant_id}")
def get_plant_detail(plant_id: str):
    plant = db.get_plant_by_id(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant

@app.get("/api/garden/map")
def get_garden_map():
    return {
        "garden_info": db.get_garden_metadata(),
        "zones": db.get_garden_zones(),
        "points_of_interest": db.get_points_of_interest(),
        "plants": db.get_all_plants()
    }

@app.get("/api/samples")
def get_sample_images():
    samples = []
    plants = db.get_all_plants()
    for p in plants:
        p_id = p["id"]
        sample_filename = f"{p_id}.jpg"
        sample_path = os.path.join(SAMPLES_DIR, sample_filename)
        if os.path.exists(sample_path):
            samples.append({
                "plant_id": p_id,
                "common_name": p["common_name"],
                "scientific_name": p["scientific_name"],
                "url": f"/samples/{sample_filename}",
                "zone_name": p["zone_name"]
            })
    return samples

@app.post("/api/identify")
async def identify_plant(
    file: UploadFile = File(None),
    image_base64: str = Form(None),
    visitor_lat: float = Form(None),
    visitor_lng: float = Form(None)
):
    """
    Core PRCV Plant Identification Endpoint with Weighted Ensemble Consensus.
    Combines MobileNetV2 Transfer Learning with SVM and Random Forest for high accuracy on real photos.
    """
    img_bgr = parse_input_image(file, image_base64)

    # 1. Deep CNN Inference (MobileNetV2 Transfer Learning)
    cnn_pred = cnn_classifier.predict_image(img_bgr)
    deep_emb = cnn_pred.get("embedding")

    # 2. Classical ML Inference (SVM, KNN, RF) using hybrid handcrafted + deep features
    classical_pred = classical_classifier.predict_image(img_bgr, deep_embedding=deep_emb)

    # 3. Weighted Ensemble Consensus
    all_plants = db.get_all_plants()
    ensemble_scores = {}
    for p in all_plants:
        pid = p["id"]
        p_cnn = float(cnn_pred["all_probs"].get(pid, 0.0))
        p_svm = float(classical_pred["svm"]["all_probs"].get(pid, 0.0))
        p_rf = float(classical_pred["random_forest"]["all_probs"].get(pid, 0.0))

        # 50% Transfer CNN + 30% SVM + 20% Random Forest
        ensemble_scores[pid] = (0.50 * p_cnn) + (0.30 * p_svm) + (0.20 * p_rf)

    sorted_candidates = sorted(ensemble_scores.items(), key=lambda x: x[1], reverse=True)
    best_id = sorted_candidates[0][0]
    plant_info = db.get_plant_by_id(best_id)

    top3_ensemble = [
        {"plant_id": cand[0], "confidence": round(cand[1] * 100, 2)}
        for cand in sorted_candidates[:3]
    ]

    # 4. Pathfinding / Navigation to the plant
    visitor_coords = None
    if visitor_lat is not None and visitor_lng is not None:
        visitor_coords = {"lat": visitor_lat, "lng": visitor_lng}

    route_data = None
    try:
        route_data = navigator.navigate_to_plant(
            target_plant_id=best_id,
            start_node_id="N_ENTRANCE",
            visitor_coords=visitor_coords
        )
    except Exception as e:
        print(f"Route calculation note: {e}")

    return {
        "status": "success",
        "predicted_plant": plant_info,
        "models": {
            "svm": {
                "predicted_id": classical_pred["svm"]["predicted_id"],
                "confidence": classical_pred["svm"]["confidence"],
                "top3": classical_pred["svm"]["top3"]
            },
            "knn": classical_pred["knn"],
            "random_forest": {
                "predicted_id": classical_pred["random_forest"]["predicted_id"],
                "confidence": classical_pred["random_forest"]["confidence"]
            },
            "cnn": {
                "predicted_id": cnn_pred["predicted_id"],
                "confidence": cnn_pred["confidence"],
                "top3": cnn_pred["top3"]
            },
            "ensemble": {
                "predicted_id": best_id,
                "confidence": round(sorted_candidates[0][1] * 100, 2),
                "top3": top3_ensemble
            }
        },
        "extracted_features_summary": {
            "dominant_colors": classical_pred["features"]["dominant_colors"],
            "glcm_texture": classical_pred["features"]["texture_features"]["glcm_stats"],
            "shape_metrics": classical_pred["features"]["shape_features"]["stats"],
            "feature_dim": classical_pred["features"]["feature_dim"]
        },
        "navigation_route": route_data
    }

@app.post("/api/prcv/pipeline")
async def prcv_pipeline_inspection(
    file: UploadFile = File(None),
    image_base64: str = Form(None)
):
    img_bgr = parse_input_image(file, image_base64)
    visual_steps = generate_pipeline_visuals(img_bgr)
    feature_data = extract_all_features(img_bgr)

    return {
        "visual_stages": visual_steps,
        "features": {
            "dominant_colors": feature_data["dominant_colors"],
            "h_hist_curve": feature_data["color_features"]["h_hist_curve"],
            "s_hist_curve": feature_data["color_features"]["s_hist_curve"],
            "v_hist_curve": feature_data["color_features"]["v_hist_curve"],
            "glcm_stats": feature_data["texture_features"]["glcm_stats"],
            "lbp_hist_curve": feature_data["texture_features"]["lbp_hist_curve"],
            "shape_stats": feature_data["shape_features"]["stats"]
        }
    }

@app.post("/api/visual-search")
async def visual_plant_search(
    file: UploadFile = File(None),
    image_base64: str = Form(None),
    top_k: int = Query(5, description="Number of visual matches to return")
):
    img_bgr = parse_input_image(file, image_base64)
    # Extract deep embedding for search
    deep_emb = None
    if cnn_classifier.is_trained:
        try:
            deep_res = cnn_classifier.predict_image(img_bgr)
            deep_emb = deep_res.get("embedding")
        except Exception as e:
            print("Deep embedding for visual search note:", e)

    plants_db_dict = {p["id"]: p for p in db.get_all_plants()}
    search_res = visual_search_engine.search_by_image(img_bgr, plants_db_dict, deep_embedding=deep_emb, top_k=top_k)
    return search_res

@app.get("/api/navigate")
def get_navigation_route(
    plant_id: str = Query(..., description="Target plant ID to navigate to"),
    start_node: str = Query("N_ENTRANCE", description="Starting graph node ID"),
    lat: float = Query(None, description="Visitor current latitude"),
    lng: float = Query(None, description="Visitor current longitude")
):
    visitor_coords = None
    if lat is not None and lng is not None:
        visitor_coords = {"lat": lat, "lng": lng}

    try:
        route = navigator.navigate_to_plant(
            target_plant_id=plant_id,
            start_node_id=start_node,
            visitor_coords=visitor_coords
        )
        return route
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/tours")
def get_tours():
    return db.get_themed_tours()

@app.get("/api/tours/{tour_id}/route")
def get_tour_route(tour_id: str):
    try:
        return navigator.plan_themed_tour(tour_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/prcv/metrics")
def get_academic_metrics():
    global eval_metrics_data
    if not eval_metrics_data:
        metrics_file = os.path.join(MODELS_DIR, "prcv_evaluation_metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                eval_metrics_data = json.load(f)
    return eval_metrics_data

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/samples", StaticFiles(directory="samples"), name="samples")
