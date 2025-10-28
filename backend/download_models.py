import os
import requests
from pathlib import Path

def download_file(url: str, local_path: str):
    """Download file from URL to local path"""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✅ Downloaded: {local_path}")

# Create model directories
os.makedirs("models/text_classifier", exist_ok=True)
os.makedirs("models/image_classifier", exist_ok=True)

print("📥 Downloading model files from Kaggle...")

# You'll need to provide the direct download URLs from your public Kaggle datasets
# Format: https://www.kaggle.com/datasets/[username]/[dataset]/download?datasetVersionNumber=[version]

print("⚠️  Please provide direct download URLs for your model files from Kaggle")
print("Or manually download and place files in:")
print("- models/text_classifier/")
print("- models/image_classifier/")
