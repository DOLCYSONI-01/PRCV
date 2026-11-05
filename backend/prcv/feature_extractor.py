"""
Feature Extraction Module for PRCV.
Extracts handcrafted visual descriptors:
1. Color Features: HSV Color Histograms & Color Moments
2. Texture Features: GLCM Haralick Features & Local Binary Patterns (LBP)
3. Shape Features: Hu Invariant Moments & Morphological Descriptors
"""

import cv2
import numpy as np
from scipy import stats
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from backend.prcv.preprocessor import segment_plant_foreground

def extract_color_features(image_bgr: np.ndarray, mask: np.ndarray = None):
    """
    Extract Color Descriptors:
    - Normalized HSV Histograms: H (32 bins), S (16 bins), V (16 bins)
    - Color Moments: Mean, Std Dev, and Skewness for H, S, and V channels
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    # 1. HSV Histograms
    h_hist = cv2.calcHist([hsv], [0], mask, [32], [0, 180])
    s_hist = cv2.calcHist([hsv], [1], mask, [16], [0, 256])
    v_hist = cv2.calcHist([hsv], [2], mask, [16], [0, 256])

    # Normalize histograms to unit sum
    h_hist = cv2.normalize(h_hist, h_hist).flatten()
    s_hist = cv2.normalize(s_hist, s_hist).flatten()
    v_hist = cv2.normalize(v_hist, v_hist).flatten()

    hist_features = np.concatenate([h_hist, s_hist, v_hist])

    # 2. Color Moments (Mean, Std Dev, Skewness)
    if mask is not None and np.any(mask > 0):
        h_vals = hsv[:, :, 0][mask > 0]
        s_vals = hsv[:, :, 1][mask > 0]
        v_vals = hsv[:, :, 2][mask > 0]
    else:
        h_vals = hsv[:, :, 0].flatten()
        s_vals = hsv[:, :, 1].flatten()
        v_vals = hsv[:, :, 2].flatten()

    moments = []
    for vals in [h_vals, s_vals, v_vals]:
        if len(vals) > 0:
            m_mean = float(np.mean(vals))
            m_std = float(np.std(vals))
            m_skew = float(stats.skew(vals)) if len(vals) > 2 and m_std > 1e-4 else 0.0
        else:
            m_mean, m_std, m_skew = 0.0, 0.0, 0.0
        moments.extend([m_mean, m_std, m_skew])

    moments = np.array(moments, dtype=np.float32)

    # Dominant colors for UI visualization (in RGB hex format)
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    if mask is not None and np.any(mask > 0):
        pixels = rgb[mask > 0]
    else:
        pixels = rgb.reshape(-1, 3)

    if len(pixels) > 50:
        pixels_sample = pixels[np.random.choice(len(pixels), min(500, len(pixels)), replace=False)].astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(pixels_sample, 3, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
        dominant_colors = [f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}" for c in centers]
    else:
        dominant_colors = ["#2d6a4f", "#52b788", "#d8f3dc"]

    return {
        "hist_features": hist_features,
        "moments": moments,
        "dominant_colors": dominant_colors,
        "h_hist_curve": [float(x) for x in h_hist],
        "s_hist_curve": [float(x) for x in s_hist],
        "v_hist_curve": [float(x) for x in v_hist]
    }

def extract_texture_features(gray_img: np.ndarray, mask: np.ndarray = None):
    """
    Extract Texture Descriptors:
    - GLCM (Gray-Level Co-occurrence Matrix) Haralick statistics at distances [1, 3]
      averaged over angles [0, 45, 90, 135 degrees]:
      Contrast, Dissimilarity, Homogeneity, Energy, Correlation, ASM
    - Local Binary Patterns (LBP) uniform histogram (10 bins)
    """
    # Downscale intensity levels to 32 to speed up GLCM computation
    quantized_gray = (gray_img / 8).astype(np.uint8)

    # Distances 1 and 3 pixels
    distances = [1, 3]
    angles = [0, np.pi/4, np.pi/2, 3*np.pi/4]

    glcm = graycomatrix(quantized_gray, distances=distances, angles=angles, levels=32, symmetric=True, normed=True)

    glcm_stats = []
    glcm_dict = {}
    for prop in ['contrast', 'dissimilarity', 'homogeneity', 'energy', 'correlation', 'ASM']:
        val = graycoprops(glcm, prop)
        # Average across angles for each distance
        for d_idx, dist in enumerate(distances):
            mean_prop_dist = float(np.mean(val[d_idx, :]))
            glcm_stats.append(mean_prop_dist)
            glcm_dict[f"{prop}_d{dist}"] = round(mean_prop_dist, 4)

    glcm_features = np.array(glcm_stats, dtype=np.float32)

    # Local Binary Patterns (LBP) - Texture micro-patterns
    radius = 1
    n_points = 8 * radius
    lbp = local_binary_pattern(gray_img, n_points, radius, method='uniform')

    # Calculate LBP histogram
    lbp_bins = n_points + 2  # 10 bins for uniform LBP
    if mask is not None and np.any(mask > 0):
        lbp_vals = lbp[mask > 0]
    else:
        lbp_vals = lbp.flatten()

    lbp_hist, _ = np.histogram(lbp_vals, bins=lbp_bins, range=(0, lbp_bins), density=True)
    lbp_features = np.array(lbp_hist, dtype=np.float32)

    return {
        "glcm_features": glcm_features,
        "lbp_features": lbp_features,
        "glcm_stats": glcm_dict,
        "lbp_hist_curve": [float(x) for x in lbp_hist]
    }

def extract_shape_features(contour, image_shape):
    """
    Extract Morphological & Contour Shape Descriptors:
    - 7 Hu Moments (log-transformed for scale and rotation invariance)
    - Aspect Ratio (w / h)
    - Extent (Contour Area / Bounding Box Area)
    - Solidity (Contour Area / Convex Hull Area)
    - Circularity (4 * pi * Area / Perimeter^2)
    """
    h_img, w_img = image_shape[:2]

    if contour is None or len(contour) < 5:
        # Default fallback if no clear contour
        hu_moments = np.zeros(7, dtype=np.float32)
        shape_stats = {
            "aspect_ratio": 1.0,
            "extent": 0.5,
            "solidity": 0.5,
            "circularity": 0.5
        }
        return {
            "hu_moments": hu_moments,
            "shape_ratios": np.array([1.0, 0.5, 0.5, 0.5], dtype=np.float32),
            "stats": shape_stats
        }

    # 1. Hu Moments
    moments = cv2.moments(contour)
    raw_hu = cv2.HuMoments(moments).flatten()

    # Log transform to bring magnitudes into comparable ranges:
    # -sign(h) * log10(abs(h) + 1e-10)
    hu_moments = []
    for h in raw_hu:
        if abs(h) > 1e-10:
            val = -np.sign(h) * np.log10(abs(h))
        else:
            val = 0.0
        hu_moments.append(float(val))
    hu_moments = np.array(hu_moments, dtype=np.float32)

    # 2. Shape Ratios
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    x, y, w, h = cv2.boundingRect(contour)

    # Aspect Ratio
    aspect_ratio = float(w) / float(h) if h > 0 else 1.0

    # Extent
    rect_area = float(w * h)
    extent = float(area) / rect_area if rect_area > 0 else 0.0

    # Solidity
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    solidity = float(area) / float(hull_area) if hull_area > 0 else 0.0

    # Circularity
    if perimeter > 0:
        circularity = float(4.0 * np.pi * area) / float(perimeter * perimeter)
    else:
        circularity = 0.0

    shape_ratios = np.array([aspect_ratio, extent, solidity, circularity], dtype=np.float32)

    shape_stats = {
        "aspect_ratio": round(aspect_ratio, 3),
        "extent": round(extent, 3),
        "solidity": round(solidity, 3),
        "circularity": round(circularity, 3),
        "hu_moments": [round(float(m), 3) for m in hu_moments]
    }

    return {
        "hu_moments": hu_moments,
        "shape_ratios": shape_ratios,
        "stats": shape_stats
    }

def extract_all_features(image_bgr: np.ndarray):
    """
    Master feature extraction pipeline.
    Combines Color + Texture + Shape descriptors into a single feature vector
    and returns comprehensive breakdown for UI inspection.
    """
    # Resize to standard size (224x224)
    resized_bgr = cv2.resize(image_bgr, (224, 224), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

    # Foreground segmentation
    seg_result = segment_plant_foreground(resized_bgr)
    mask = seg_result["mask"]
    contour = seg_result["contour"]

    # 1. Color features (histograms + moments)
    color_res = extract_color_features(resized_bgr, mask=mask)
    color_vec = np.concatenate([color_res["hist_features"], color_res["moments"]])

    # 2. Texture features (GLCM + LBP)
    texture_res = extract_texture_features(gray, mask=mask)
    texture_vec = np.concatenate([texture_res["glcm_features"], texture_res["lbp_features"]])

    # 3. Shape features (Hu moments + morphometrics)
    shape_res = extract_shape_features(contour, resized_bgr.shape)
    shape_vec = np.concatenate([shape_res["hu_moments"], shape_res["shape_ratios"]])

    # Full concatenated feature vector
    full_vector = np.concatenate([color_vec, texture_vec, shape_vec]).astype(np.float32)

    return {
        "vector": full_vector,
        "feature_dim": len(full_vector),
        "color_features": color_res,
        "texture_features": texture_res,
        "shape_features": shape_res,
        "dominant_colors": color_res["dominant_colors"],
        "segmented_mask": mask,
        "primary_contour": contour
    }
