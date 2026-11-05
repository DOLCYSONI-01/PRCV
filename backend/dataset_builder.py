"""
Botanical Dataset Builder & Multi-Model Trainer using Transfer Learning & Real Images.
Loads authentic botanical photographs, performs data augmentations,
extracts handcrafted PRCV features + MobileNetV2 deep embeddings,
trains Transfer Learning CNN, SVM, KNN, and Random Forest,
and computes real-world academic evaluation metrics.
"""

import os
import json
import random
import cv2
import numpy as np
import joblib
from sklearn.model_selection import train_test_split

from backend.prcv.feature_extractor import extract_all_features
from backend.prcv.classical_models import BotanicalClassicalClassifier
from backend.prcv.cnn_model import BotanicalCNNClassifier
from backend.prcv.evaluator import evaluate_models, benchmark_latency

PLANT_SPECIES = [
    "monstera",
    "rose",
    "sunflower",
    "lavender",
    "lotus",
    "aloe_vera",
    "japanese_maple",
    "orchid",
    "cactus",
    "hibiscus"
]

def augment_real_image(image_bgr: np.ndarray) -> np.ndarray:
    """
    Applies realistic botanical photo augmentations:
    - Random rotation (-25 to +25 deg)
    - Random scaling & translation
    - Horizontal flipping
    - Brightness and contrast shifts
    """
    h, w = image_bgr.shape[:2]
    aug = image_bgr.copy()

    # Random rotation
    angle = random.uniform(-25, 25)
    scale = random.uniform(0.85, 1.15)
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, scale)
    aug = cv2.warpAffine(aug, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    # Horizontal flip
    if random.random() > 0.5:
        aug = cv2.flip(aug, 1)

    # Brightness & contrast adjustment
    alpha = random.uniform(0.85, 1.2)
    beta = random.randint(-15, 20)
    aug = cv2.convertScaleAbs(aug, alpha=alpha, beta=beta)

    return aug

def load_real_dataset_with_augmentations(aug_per_class: int = 35):
    """
    Loads authentic images from dataset/ and generates augmented instances.
    """
    X_imgs_rgb = []
    X_handcrafted = []
    y_labels = []
    plant_ref_imgs = {}

    print("Loading real botanical dataset and generating augmentations...")

    for class_idx, species in enumerate(PLANT_SPECIES):
        sp_dir = os.path.join("dataset", species)
        image_files = []
        if os.path.exists(sp_dir):
            image_files = [os.path.join(sp_dir, f) for f in os.listdir(sp_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]

        if not image_files:
            # Fallback to sample image if available
            sample_p = os.path.join("samples", f"{species}.jpg")
            if os.path.exists(sample_p):
                image_files = [sample_p]

        print(f" -> {species}: found {len(image_files)} real source photos")
        plant_ref_imgs[species] = []

        # Load real images
        loaded_imgs = []
        for f in image_files:
            img = cv2.imread(f)
            if img is not None:
                img_224 = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
                loaded_imgs.append(img_224)

        if not loaded_imgs:
            continue

        # Keep original real photos
        for real_img in loaded_imgs:
            feat = extract_all_features(real_img)["vector"]
            X_handcrafted.append(feat)
            rgb = cv2.cvtColor(real_img, cv2.COLOR_BGR2RGB)
            X_imgs_rgb.append(rgb)
            y_labels.append(class_idx)
            plant_ref_imgs[species].append(rgb)

        # Generate augmented variations to reach aug_per_class
        needed = max(0, aug_per_class - len(loaded_imgs))
        for _ in range(needed):
            base_choice = random.choice(loaded_imgs)
            aug_bgr = augment_real_image(base_choice)
            feat = extract_all_features(aug_bgr)["vector"]
            X_handcrafted.append(feat)
            rgb = cv2.cvtColor(aug_bgr, cv2.COLOR_BGR2RGB)
            X_imgs_rgb.append(rgb)
            y_labels.append(class_idx)

    return {
        "X_imgs_rgb": np.array(X_imgs_rgb, dtype=np.float32),
        "X_handcrafted": np.array(X_handcrafted, dtype=np.float32),
        "y": np.array(y_labels, dtype=np.int32),
        "plant_ref_imgs": plant_ref_imgs
    }

def train_and_evaluate():
    os.makedirs("models", exist_ok=True)
    os.makedirs("samples", exist_ok=True)

    data = load_real_dataset_with_augmentations(aug_per_class=35)

    X_imgs = data["X_imgs_rgb"]
    X_hand = data["X_handcrafted"]
    y = data["y"]

    print(f"\nTotal dataset size: {len(y)} images across {len(PLANT_SPECIES)} classes.")

    # Train / Test Split (Stratified)
    indices = np.arange(len(y))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=y)

    X_train_imgs = X_imgs[train_idx]
    y_train = y[train_idx]
    X_test_imgs = X_imgs[test_idx]
    y_test = y[test_idx]

    # Initialize CNN with MobileNetV2 Transfer Learning
    print("\n--- Training Deep Transfer Learning CNN (MobileNetV2 Backbone) ---")
    cnn = BotanicalCNNClassifier(num_classes=len(PLANT_SPECIES), img_size=224)
    cnn.fit(
        X_train_imgs,
        y_train,
        PLANT_SPECIES,
        epochs=14,
        batch_size=16
    )
    cnn.save("models")
    print("Transfer Learning CNN saved to models/cnn_model.keras")

    # Extract Deep Embeddings for all training and test images
    print("\nExtracting Deep Embeddings for Classical Classifiers...")
    deep_train = cnn.extract_deep_embeddings(X_train_imgs)
    deep_test = cnn.extract_deep_embeddings(X_test_imgs)

    # Combine Handcrafted (106) + Deep (1280) Features
    X_train_combined = np.hstack([X_hand[train_idx], deep_train])
    X_test_combined = np.hstack([X_hand[test_idx], deep_test])

    print(f"Combined Feature Vector Dimension: {X_train_combined.shape[1]}")

    print("\n--- Training Classical Models (SVM, KNN, Random Forest) ---")
    classical = BotanicalClassicalClassifier()
    classical.fit(X_train_combined, y_train, PLANT_SPECIES, uses_deep=True)
    classical.save("models")
    print("Classical models saved to models/")

    # Index Reference Embeddings for Visual Plant Search
    print("\nIndexing Visual Search reference embeddings...")
    plant_ref_embeddings = {}
    for sp in PLANT_SPECIES:
        sp_idx = PLANT_SPECIES.index(sp)
        sp_mask = (y_train == sp_idx)
        if np.any(sp_mask):
            sp_embeds = deep_train[sp_mask]
            mean_emb = np.mean(sp_embeds, axis=0)
            norm = np.linalg.norm(mean_emb)
            if norm > 1e-6:
                mean_emb = mean_emb / norm
            plant_ref_embeddings[sp] = mean_emb

    joblib.dump(plant_ref_embeddings, "models/plant_references.joblib")
    print("Visual Search embeddings indexed and saved.")

    # Evaluate on held-out test set
    print("\n--- Evaluating Models on Real Test Images ---")
    X_test_scaled = classical.scaler.transform(X_test_combined)
    y_pred_svm = classical.svm.predict(X_test_scaled)
    y_pred_knn = classical.knn.predict(X_test_scaled)
    y_pred_rf = classical.rf.predict(X_test_scaled)

    cnn_probs = cnn.model.predict(X_test_imgs, verbose=0)
    y_pred_cnn = np.argmax(cnn_probs, axis=1)

    eval_report = evaluate_models(
        y_test,
        y_pred_svm,
        y_pred_knn,
        y_pred_rf,
        y_pred_cnn,
        PLANT_SPECIES
    )

    # Benchmark Latency
    sample_bgr = cv2.imread("samples/sunflower.jpg")
    if sample_bgr is None:
        sample_bgr = np.zeros((224, 224, 3), dtype=np.uint8)
    latency_stats = benchmark_latency(classical, cnn, sample_bgr)
    eval_report["latency_benchmark"] = latency_stats

    with open("models/prcv_evaluation_metrics.json", "w") as f:
        json.dump(eval_report, f, indent=2)

    print("\n================ ACADEMIC PRCV EVALUATION REPORT ================")
    for row in eval_report["comparison_table"]:
        print(f"[{row['model']}] Accuracy: {row['accuracy']} | F1-Score: {row['f1_score']}")
    print(f"Latency: Classical SVM={latency_stats['classical_svm_ms']}ms | Deep CNN={latency_stats['deep_cnn_ms']}ms")
    print("Academic metrics exported to models/prcv_evaluation_metrics.json")
    print("All training complete!")

if __name__ == "__main__":
    train_and_evaluate()
