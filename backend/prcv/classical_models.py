"""
Classical Machine Learning Models for Plant Classification.
Implements:
- Support Vector Machine (SVM with RBF kernel)
- K-Nearest Neighbors (KNN)
- Random Forest Classifier (RF)
Uses StandardScaler on handcrafted and deep feature vectors.
"""

import os
import joblib
import numpy as np
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from backend.prcv.feature_extractor import extract_all_features

class BotanicalClassicalClassifier:
    def __init__(self):
        self.scaler = StandardScaler()
        self.svm = SVC(kernel='rbf', C=10.0, gamma='scale', probability=True, random_state=42)
        self.knn = KNeighborsClassifier(n_neighbors=3, weights='distance')
        self.rf = RandomForestClassifier(n_estimators=100, random_state=42)
        self.class_names = []
        self.is_trained = False
        self.uses_deep_features = False

    def fit(self, X: np.ndarray, y: list, class_names: list, uses_deep: bool = True):
        """Train scaler and all 3 classical classifiers."""
        self.class_names = list(class_names)
        self.uses_deep_features = uses_deep
        X_scaled = self.scaler.fit_transform(X)

        self.svm.fit(X_scaled, y)
        self.knn.fit(X_scaled, y)
        self.rf.fit(X_scaled, y)
        self.is_trained = True

    def predict_image(self, image_bgr: np.ndarray, deep_embedding: np.ndarray = None):
        """
        Extract features from input image, scale, and predict with SVM, KNN, and Random Forest.
        Returns detailed predictions and top candidates.
        """
        if not self.is_trained:
            raise RuntimeError("Classifier has not been trained or loaded yet.")

        feature_res = extract_all_features(image_bgr)
        feat_vec = feature_res["vector"]

        if self.uses_deep_features and deep_embedding is not None:
            feat_combined = np.concatenate([feat_vec, np.array(deep_embedding, dtype=np.float32)])
        else:
            feat_combined = feat_vec

        feat_scaled = self.scaler.transform(feat_combined.reshape(1, -1))

        # 1. SVM Probabilities
        svm_probs = self.svm.predict_proba(feat_scaled)[0]
        svm_pred_idx = int(np.argmax(svm_probs))
        svm_pred_class = self.class_names[svm_pred_idx]
        svm_top3_indices = np.argsort(svm_probs)[::-1][:3]
        svm_top3 = [
            {"plant_id": self.class_names[i], "confidence": round(float(svm_probs[i]) * 100, 2)}
            for i in svm_top3_indices
        ]

        # 2. KNN Probabilities
        knn_probs = self.knn.predict_proba(feat_scaled)[0]
        knn_pred_idx = int(np.argmax(knn_probs))
        knn_pred_class = self.class_names[knn_pred_idx]

        # 3. Random Forest Probabilities
        rf_probs = self.rf.predict_proba(feat_scaled)[0]
        rf_pred_idx = int(np.argmax(rf_probs))
        rf_pred_class = self.class_names[rf_pred_idx]

        return {
            "features": feature_res,
            "svm": {
                "predicted_id": svm_pred_class,
                "confidence": round(float(svm_probs[svm_pred_idx]) * 100, 2),
                "top3": svm_top3,
                "all_probs": {self.class_names[i]: float(svm_probs[i]) for i in range(len(self.class_names))}
            },
            "knn": {
                "predicted_id": knn_pred_class,
                "confidence": round(float(knn_probs[knn_pred_idx]) * 100, 2)
            },
            "random_forest": {
                "predicted_id": rf_pred_class,
                "confidence": round(float(rf_probs[rf_pred_idx]) * 100, 2),
                "all_probs": {self.class_names[i]: float(rf_probs[i]) for i in range(len(self.class_names))}
            }
        }

    def save(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        joblib.dump(self.scaler, os.path.join(directory, "scaler.joblib"))
        joblib.dump(self.svm, os.path.join(directory, "svm_model.joblib"))
        joblib.dump(self.knn, os.path.join(directory, "knn_model.joblib"))
        joblib.dump(self.rf, os.path.join(directory, "rf_model.joblib"))
        joblib.dump(self.class_names, os.path.join(directory, "class_names.joblib"))
        joblib.dump(self.uses_deep_features, os.path.join(directory, "uses_deep.joblib"))

    def load(self, directory: str):
        self.scaler = joblib.load(os.path.join(directory, "scaler.joblib"))
        self.svm = joblib.load(os.path.join(directory, "svm_model.joblib"))
        self.knn = joblib.load(os.path.join(directory, "knn_model.joblib"))
        self.rf = joblib.load(os.path.join(directory, "rf_model.joblib"))
        self.class_names = joblib.load(os.path.join(directory, "class_names.joblib"))
        uses_deep_path = os.path.join(directory, "uses_deep.joblib")
        if os.path.exists(uses_deep_path):
            self.uses_deep_features = joblib.load(uses_deep_path)
        self.is_trained = True
