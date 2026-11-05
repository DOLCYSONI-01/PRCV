"""
Real Botanical Image Dataset Fetcher.
Downloads authentic photographs for the 10 botanical garden species from Wikimedia Commons
to ensure high real-world accuracy on user uploads.
"""

import os
import requests
import cv2
import numpy as np

HEADERS = {
    'User-Agent': 'BotanicalNavigator/1.0 (academic-research@botanical.local)'
}

SPECIES_QUERIES = {
    "monstera": [
        "Monstera deliciosa leaf",
        "Monstera deliciosa plant",
        "Monstera deliciosa foliage"
    ],
    "rose": [
        "Rosa gallica flower",
        "French rose bloom",
        "Rosa gallica blossom"
    ],
    "sunflower": [
        "Helianthus annuus flower",
        "Common sunflower bloom",
        "Sunflower yellow petals"
    ],
    "lavender": [
        "Lavandula angustifolia flower",
        "English lavender spike",
        "Lavender field bloom"
    ],
    "lotus": [
        "Nelumbo nucifera flower",
        "Sacred lotus pink bloom",
        "Nelumbo nucifera pond"
    ],
    "aloe_vera": [
        "Aloe vera plant",
        "Aloe vera succulent leaves",
        "Aloe vera foliage"
    ],
    "japanese_maple": [
        "Acer palmatum leaves",
        "Japanese maple red leaf",
        "Acer palmatum foliage"
    ],
    "orchid": [
        "Phalaenopsis amabilis orchid",
        "Moth orchid flower",
        "Phalaenopsis blossom"
    ],
    "cactus": [
        "Echinocactus grusonii cactus",
        "Golden barrel cactus spines",
        "Echinocactus grusonii succulent"
    ],
    "hibiscus": [
        "Hibiscus rosa-sinensis flower",
        "Tropical hibiscus red bloom",
        "Hibiscus blossom"
    ]
}

def search_commons_images(query: str, limit: int = 8):
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|thumburl",
        "iiurlwidth": 400,
        "format": "json"
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=12)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        urls = []
        for p in pages.values():
            info = p.get("imageinfo", [])
            if info:
                thumb = info[0].get("thumburl") or info[0].get("url")
                if thumb and (thumb.endswith('.jpg') or thumb.endswith('.png') or thumb.endswith('.jpeg')):
                    urls.append(thumb)
        return urls
    except Exception as e:
        print(f"Search error for {query}: {e}")
        return []

def download_and_save_image(url: str, save_path: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.content) > 3000:
            arr = np.frombuffer(r.content, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None and img.shape[0] > 100 and img.shape[1] > 100:
                resized = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
                cv2.imwrite(save_path, resized)
                return True
    except Exception as e:
        pass
    return False

def build_real_dataset():
    base_dir = "dataset"
    samples_dir = "samples"
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(samples_dir, exist_ok=True)

    print("Fetching authentic real-world botanical photos for 10 species...")

    for species, queries in SPECIES_QUERIES.items():
        species_dir = os.path.join(base_dir, species)
        os.makedirs(species_dir, exist_ok=True)

        downloaded = 0
        target = 10
        print(f"\nSearching photos for: {species}...")

        # Also check Wikipedia page summary first for guaranteed primary specimen
        try:
            summary_name = {
                'monstera': 'Monstera_deliciosa', 'rose': 'Rosa_gallica',
                'sunflower': 'Helianthus_annuus', 'lavender': 'Lavandula_angustifolia',
                'lotus': 'Nelumbo_nucifera', 'aloe_vera': 'Aloe_vera',
                'japanese_maple': 'Acer_palmatum', 'orchid': 'Phalaenopsis_amabilis',
                'cactus': 'Echinocactus_grusonii', 'hibiscus': 'Hibiscus_rosa-sinensis'
            }.get(species)

            sr = requests.get(f'https://en.wikipedia.org/api/rest_v1/page/summary/{summary_name}', headers=HEADERS, timeout=8)
            primary_thumb = sr.json().get('thumbnail', {}).get('source')
            if primary_thumb:
                save_p = os.path.join(species_dir, f"specimen_0.jpg")
                if download_and_save_image(primary_thumb, save_p):
                    downloaded += 1
                    # Also copy to samples/ as the clean reference sample for the web UI
                    cv2.imwrite(os.path.join(samples_dir, f"{species}.jpg"), cv2.imread(save_p))
                    print(f" -> Got primary specimen for {species}")
        except Exception as e:
            print(f" -> Notice fetching primary: {e}")

        # Fetch additional photos via queries
        for q in queries:
            if downloaded >= target:
                break
            urls = search_commons_images(q, limit=6)
            for u in urls:
                if downloaded >= target:
                    break
                save_p = os.path.join(species_dir, f"specimen_{downloaded}.jpg")
                if download_and_save_image(u, save_p):
                    downloaded += 1
                    print(f"    Downloaded {species} image {downloaded}/{target}")

        print(f"Total authentic images for {species}: {downloaded}")

if __name__ == "__main__":
    build_real_dataset()
