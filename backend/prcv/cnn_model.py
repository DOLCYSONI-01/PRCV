"""
Deep Transfer Learning Model for Plant Identification.
Uses ImageNet-pretrained MobileNetV2 architecture with a specialized botanical classification head.
Achieves high generalization and accuracy on real-world photos.
"""

import os
import json
import numpy as np
import cv2

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import mobilenet_v2

class BotanicalCNNClassifier:
    def __init__(self, num_classes: int = 10, img_size: int = 224):
        self.img_size = img_size
        self.num_classes = num_classes
        self.model = None
        self.feature_extractor = None
        self.class_names = []
        self.is_trained = False

    def build_model(self):
        """Builds Transfer Learning model with frozen MobileNetV2 backbone."""
        base_mobilenet = mobilenet_v2.MobileNetV2(
            input_shape=(self.img_size, self.img_size, 3),
            include_top=False,
            weights='imagenet',
            pooling='avg'
        )
        base_mobilenet.trainable = False

        self.feature_extractor = base_mobilenet

        inputs = keras.Input(shape=(self.img_size, self.img_size, 3))
        # Preprocessing standard for MobileNetV2 (maps [0, 255] to [-1, 1])
        preprocessed = mobilenet_v2.preprocess_input(inputs)
        features = base_mobilenet(preprocessed, training=False)

        x = layers.Dense(256, activation='relu', kernel_regularizer=keras.regularizers.l2(1e-4))(features)
        x = layers.BatchNormalization()(x)
        x = layers.Dropout(0.35)(x)
        x = layers.Dense(128, activation='relu')(x)
        outputs = layers.Dense(self.num_classes, activation='softmax', name='species_prediction')(x)

        self.model = keras.Model(inputs=inputs, outputs=outputs)
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-3),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        return self.model

    def extract_deep_embeddings(self, images_rgb: np.ndarray) -> np.ndarray:
        """Extracts 1280-dim feature vectors from MobileNetV2 backbone."""
        if self.feature_extractor is None:
            self.build_model()
        preprocessed = mobilenet_v2.preprocess_input(images_rgb.astype(np.float32))
        return self.feature_extractor.predict(preprocessed, verbose=0)

    def fit(self, X_images_rgb: np.ndarray, y_labels: np.ndarray, class_names: list, epochs: int = 15, batch_size: int = 16):
        """Fine-tunes the classification head on plant images."""
        self.class_names = list(class_names)
        self.num_classes = len(self.class_names)
        self.build_model()

        history = self.model.fit(
            X_images_rgb,
            y_labels,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.15,
            verbose=1
        )
        self.is_trained = True
        return history

    def predict_image(self, image_bgr: np.ndarray):
        """
        Classifies an input BGR image using Transfer Learning.
        Returns top-3 predictions, confidence, all probabilities, and deep embedding.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("CNN model has not been trained or loaded yet.")

        resized_bgr = cv2.resize(image_bgr, (self.img_size, self.img_size), interpolation=cv2.INTER_AREA)
        resized_rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
        input_tensor = np.expand_dims(resized_rgb.astype(np.float32), axis=0)

        probs = self.model.predict(input_tensor, verbose=0)[0]
        preprocessed = mobilenet_v2.preprocess_input(input_tensor)
        embeddings = self.feature_extractor.predict(preprocessed, verbose=0)[0]

        pred_idx = int(np.argmax(probs))
        pred_class = self.class_names[pred_idx]
        top3_indices = np.argsort(probs)[::-1][:3]
        top3 = [
            {"plant_id": self.class_names[i], "confidence": round(float(probs[i]) * 100, 2)}
            for i in top3_indices
        ]

        return {
            "predicted_id": pred_class,
            "confidence": round(float(probs[pred_idx]) * 100, 2),
            "top3": top3,
            "all_probs": {self.class_names[i]: float(probs[i]) for i in range(len(self.class_names))},
            "embedding": embeddings.tolist()
        }

    def save(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        model_path = os.path.join(directory, "cnn_model.keras")
        self.model.save(model_path)
        with open(os.path.join(directory, "cnn_classes.json"), "w") as f:
            json.dump(self.class_names, f)

    def load(self, directory: str):
        model_path = os.path.join(directory, "cnn_model.keras")
        self.model = keras.models.load_model(model_path)
        # Re-link feature extractor
        base = self.model.get_layer('mobilenetv2_1.00_224')
        self.feature_extractor = base
        with open(os.path.join(directory, "cnn_classes.json"), "r") as f:
            self.class_names = json.load(f)
        self.num_classes = len(self.class_names)
        self.is_trained = True
