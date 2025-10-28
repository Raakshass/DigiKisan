import torch
from torch import nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import pickle
import os
from typing import Optional, Dict, List, Any

# Mean pooling function
def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

# Sentence encoder model
class SentenceEncoder(nn.Module):
    def __init__(self, model_name):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        for param in self.model.parameters():
            param.requires_grad = False
        self.model.eval()

    def forward(self, texts):
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
        embeddings = mean_pooling(outputs, inputs["attention_mask"])
        return F.normalize(embeddings, p=2, dim=1)

# MLP classifier head
class ClassifierHead(nn.Module):
    def __init__(self, emb_dim=384, hidden_dim=256, num_classes=2, p_dropout=0.2):
        super().__init__()
        self.fc1 = nn.Linear(emb_dim, hidden_dim)
        self.dropout = nn.Dropout(p_dropout)
        self.fc2 = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        return self.fc2(x)

# Main text classifier for inference
class TextClassifierInference:
    def __init__(self, model_dir="models/text_classifier"):
        """
        Initialize the text classifier for inference
        
        Args:
            model_dir: Directory containing saved model files
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        try:
            # Load configuration
            with open(os.path.join(model_dir, "config.pkl"), "rb") as f:
                self.config = pickle.load(f)
            
            # Load label encoder
            with open(os.path.join(model_dir, "label_encoder.pkl"), "rb") as f:
                self.label_encoder = pickle.load(f)
            
            # Initialize sentence encoder
            self.encoder = SentenceEncoder(self.config["MODEL_NAME"]).to(self.device)
            
            # Initialize and load classifier
            head_kwargs = {
                "emb_dim": self.config["emb_dim"],
                "hidden_dim": self.config["hidden_dim"],
                "num_classes": self.config["num_classes"],
            }
            
            if "p_dropout" in self.config:
                head_kwargs["p_dropout"] = self.config["p_dropout"]

            self.classifier = ClassifierHead(**head_kwargs).to(self.device)
            
            # Load trained weights
            checkpoint = torch.load(os.path.join(model_dir, "classifier_weights.pth"), 
                                  map_location=self.device)
            self.classifier.load_state_dict(checkpoint)
            self.classifier.eval()
            
            print(f"✅ Text classifier loaded successfully!")
            print(f"   Classes: {self.config['classes']}")
            print(f"   Model name: {self.config['MODEL_NAME']}")
            print(f"   Embedding dim: {self.config['emb_dim']}")
            print(f"   Hidden dim: {self.config['hidden_dim']}")
            print(f"   Num classes: {self.config['num_classes']}")
            
        except Exception as e:
            print(f"❌ Error loading text classifier: {e}")
            raise
    
    def predict(self, text):
        """
        Predict class for a single text input
        
        Args:
            text: Input text string
        
        Returns:
            dict: Contains prediction, confidence, and probabilities
        """
        try:
            with torch.no_grad():
                # Get embeddings
                embeddings = self.encoder([text])
                
                # Get logits and probabilities
                logits = self.classifier(embeddings)
                
                # ✅ DEBUG PRINTS
                print(f"[DEBUG] Input text: '{text}'")
                print(f"[DEBUG] Embeddings shape: {embeddings.shape}")
                print(f"[DEBUG] Logits shape: {logits.shape}")
                print(f"[DEBUG] Logits values: {logits}")
                
                # Apply softmax to get probabilities
                probabilities = F.softmax(logits, dim=1)
                print(f"[DEBUG] Probabilities shape: {probabilities.shape}")
                print(f"[DEBUG] Probabilities: {probabilities}")
                
                # Get prediction
                predicted_class_idx = torch.argmax(logits, dim=1).item()
                print(f"[DEBUG] Predicted class idx: {predicted_class_idx}")
                print(f"[DEBUG] Available classes: {self.config['classes']}")
                
                # ✅ HANDLE DIMENSION MISMATCH
                if probabilities.shape[1] == 1:
                    # Single class output - handle gracefully
                    print("[DEBUG] Single class output detected - creating binary probabilities")
                    confidence = torch.sigmoid(logits[0]).item()  # Convert to probability
                    
                    # Create probabilities for both classes
                    prob_dict = {
                        self.config['classes'][0]: 1.0 - confidence,
                        self.config['classes'][1]: confidence
                    }
                    
                    # Determine prediction based on threshold
                    predicted_class = self.config['classes'][1] if confidence > 0.5 else self.config['classes']
                    
                elif probabilities.shape[1] >= 2:
                    # Normal multi-class output
                    print("[DEBUG] Multi-class output detected")
                    confidence = probabilities[0][predicted_class_idx].item()
                    predicted_class = self.label_encoder.inverse_transform([predicted_class_idx])[0]
                    
                    prob_dict = {
                        class_name: prob.item() 
                        for class_name, prob in zip(self.config['classes'], probabilities[0])
                    }
                else:
                    # Edge case: empty output
                    raise ValueError(f"Invalid model output shape: {probabilities.shape}")
                
                result = {
                    "prediction": predicted_class,
                    "confidence": confidence,
                    "probabilities": prob_dict
                }
                
                print(f"[DEBUG] Final result: {result}")
                return result
                
        except Exception as e:
            print(f"❌ Error during prediction: {e}")
            # Return a safe fallback result
            return {
                "prediction": "non_price_enquiry",
                "confidence": 0.5,
                "probabilities": {
                    "non_price_enquiry": 0.5,
                    "price_enquiry": 0.5
                },
                "error": str(e)
            }
