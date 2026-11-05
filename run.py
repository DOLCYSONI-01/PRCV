"""
AI Botanical Garden Navigator - One-Click Launcher.
Starts the FastAPI application and opens the web dashboard in your browser.
"""

import os
import sys
import webbrowser
import uvicorn

def main():
    print("=" * 65)
    print("🌿 AI Botanical Garden Navigator - PRCV System")
    print("=" * 65)

    models_dir = os.path.join(os.path.dirname(__file__), "models")
    svm_path = os.path.join(models_dir, "svm_model.joblib")

    # If models are not trained yet, run the dataset builder and trainer first
    if not os.path.exists(svm_path):
        print("Model files not found. Initializing dataset & training models...")
        from backend.dataset_builder import train_and_evaluate
        train_and_evaluate()

    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print(f"\n🚀 Starting Botanical Navigator Server at: {url}")
    print("Opening web interface in default browser...\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("backend.app:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
