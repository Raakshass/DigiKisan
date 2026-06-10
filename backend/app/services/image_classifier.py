import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import json
from pathlib import Path
from typing import List, Tuple

class UnifiedCropDiseaseClassifier(nn.Module):
    def __init__(self, num_classes: int, pretrained: bool = False):
        super().__init__()
        self.backbone = models.resnet50(pretrained=pretrained)
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        return self.backbone(x)

class CropDiseaseClassifier:
    def __init__(self, checkpoint_path: str, class_names_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.available = False
        self.class_names = []
        
        try:
            # Load class names
            with open(class_names_path, 'r') as f:
                self.class_names = json.load(f)
            
            # Check if checkpoint is a real file (not a Git LFS pointer)
            checkpoint_size = Path(checkpoint_path).stat().st_size if Path(checkpoint_path).exists() else 0
            if checkpoint_size < 1000:
                print(f"⚠️ Model checkpoint appears to be a Git LFS pointer ({checkpoint_size} bytes)")
                print(f"   Run: git lfs pull")
                return
            
            # Load model
            self.model = UnifiedCropDiseaseClassifier(
                num_classes=len(self.class_names), 
                pretrained=False
            )
            
            # Load weights
            checkpoint = torch.load(checkpoint_path, map_location=self.device)
            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            else:
                state_dict = checkpoint
                
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            
            # Preprocessing
            self.preprocess = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.CenterCrop((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            
            self.available = True
            print(f"✅ Crop disease classifier loaded with {len(self.class_names)} classes")
        except Exception as e:
            print(f"⚠️ Crop disease classifier unavailable: {e}")
            print(f"   Disease detection will use Gemini-only mode")

    def predict(self, image_path: str) -> str:
        img = Image.open(image_path).convert("RGB")
        x = self.preprocess(img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            logits = self.model(x)
            if isinstance(logits, (tuple, list)):
                logits = logits[0]
            idx = int(torch.argmax(logits, dim=1).item())
            
        return self.class_names[idx]
