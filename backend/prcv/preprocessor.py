"""
Image Preprocessing and Segmentation Module.
Handles resizing, normalization, color spaces, CLAHE contrast enhancement,
and Otsu/contour segmentation.
"""

import cv2
import numpy as np
import base64

def bgr_to_base64_jpeg(image: np.ndarray, quality: int = 85) -> str:
    """Encode an OpenCV image (BGR or single channel) to Base64 JPEG data URL."""
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buffer = cv2.imencode('.jpg', image, encode_params)
    if not success:
        return ""
    b64_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{b64_str}"

def preprocess_image(image_bgr: np.ndarray, target_size=(224, 224)):
    """
    Standardize plant image for feature extraction and deep learning.
    Resizes image, converts to RGB and HSV, and returns preprocessed dict.
    """
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Invalid image provided")

    # Resize to standard size maintaining aspect ratio with padding or direct resize
    resized_bgr = cv2.resize(image_bgr, target_size, interpolation=cv2.INTER_AREA)
    resized_rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

    return {
        "bgr": resized_bgr,
        "rgb": resized_rgb,
        "hsv": hsv,
        "gray": gray,
        "normalized_rgb": resized_rgb.astype(np.float32) / 255.0
    }

def apply_clahe(image_bgr: np.ndarray, clip_limit: float = 2.0, tile_grid_size=(8, 8)) -> np.ndarray:
    """
    Contrast Limited Adaptive Histogram Equalization (CLAHE).
    Converts image to LAB color space and applies CLAHE to the Luminance (L) channel.
    Crucial for handling variable outdoor lighting, harsh sun, or cloudy botanical gardens.
    """
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_enhanced = clahe.apply(l_channel)

    merged_lab = cv2.merge((l_enhanced, a_channel, b_channel))
    enhanced_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
    return enhanced_bgr

def segment_plant_foreground(image_bgr: np.ndarray):
    """
    Image Segmentation:
    Separates the plant/leaf/flower foreground from the background
    using Gaussian blurring, Otsu's automatic thresholding, and morphological operations.
    Returns:
        mask: Binary mask of the foreground plant
        segmented_bgr: Plant with background masked out
        largest_contour: Primary detected contour
        bounding_box: (x, y, w, h) of the primary contour
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Otsu's thresholding calculates the optimal threshold value minimizing intra-class variance
    _, otsu_thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Invert if the foreground is darker than background or check center density
    h, w = gray.shape
    center_roi = otsu_thresh[int(h*0.25):int(h*0.75), int(w*0.25):int(w*0.75)]
    if np.mean(center_roi) < 100:
        otsu_thresh = cv2.bitwise_not(otsu_thresh)

    # Morphological opening (erode followed by dilate) to remove noise speckles,
    # followed by closing to bridge small gaps within petal or leaf veins
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned_mask = cv2.morphologyEx(otsu_thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find external contours
    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_contour = None
    bbox = (0, 0, w, h)
    refined_mask = cleaned_mask.copy()

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        # Create a single clean mask containing only the primary plant object
        refined_mask = np.zeros_like(cleaned_mask)
        cv2.drawContours(refined_mask, [largest_contour], -1, 255, thickness=cv2.FILLED)
        bbox = cv2.boundingRect(largest_contour)

    segmented_bgr = cv2.bitwise_and(image_bgr, image_bgr, mask=refined_mask)

    return {
        "mask": refined_mask,
        "segmented_bgr": segmented_bgr,
        "contour": largest_contour,
        "bbox": bbox
    }

def generate_pipeline_visuals(image_bgr: np.ndarray):
    """
    Generates step-by-step visual stages for the PRCV Academic Inspection tool.
    Each stage is converted to a base64 image data URL.
    """
    # 1. Original standard resized
    resized = cv2.resize(image_bgr, (256, 256), interpolation=cv2.INTER_AREA)

    # 2. Grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # 3. CLAHE Contrast Enhanced
    clahe_img = apply_clahe(resized, clip_limit=2.5)

    # 4. Gaussian Blur (noise reduction)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)

    # 5. Otsu Binary Segmentation Mask
    seg_result = segment_plant_foreground(resized)
    mask = seg_result["mask"]

    # 6. Canny Edge Detection
    canny_edges = cv2.Canny(blurred, 40, 120)

    # 7. Contours overlay
    contour_overlay = resized.copy()
    if seg_result["contour"] is not None:
        cv2.drawContours(contour_overlay, [seg_result["contour"]], -1, (0, 255, 0), 2)
        x, y, w, h = seg_result["bbox"]
        cv2.rectangle(contour_overlay, (x, y), (x + w, y + h), (255, 100, 0), 2)

    # 8. Segmented isolated foreground
    isolated = seg_result["segmented_bgr"]

    return {
        "step_1_original": bgr_to_base64_jpeg(resized),
        "step_2_grayscale": bgr_to_base64_jpeg(gray),
        "step_3_clahe": bgr_to_base64_jpeg(clahe_img),
        "step_4_gaussian_blur": bgr_to_base64_jpeg(blurred),
        "step_5_otsu_mask": bgr_to_base64_jpeg(mask),
        "step_6_canny_edges": bgr_to_base64_jpeg(canny_edges),
        "step_7_contour_tracking": bgr_to_base64_jpeg(contour_overlay),
        "step_8_segmented_plant": bgr_to_base64_jpeg(isolated)
    }
