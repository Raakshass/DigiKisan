# 🌾 DigiKisan - AI-Powered Agricultural Assistant

<div align="center">

![DigiKisan Logo](assets/images/img_logo.png)

**Empowering Indian Farmers with AI-Driven Agricultural Insights**

[![Flutter](https://img.shields.io/badge/Flutter-3.0+-02569B?logo=flutter)](https://flutter.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#-features) • [Architecture](#-architecture) • [Installation](#-installation) • [Usage](#-usage) • [API Documentation](#-api-endpoints)

</div>

---

## 📖 About

DigiKisan is a comprehensive agricultural chatbot application designed specifically for Indian farmers. It combines a Flutter mobile frontend with a powerful FastAPI backend to provide real-time market prices, crop disease detection, and intelligent voice-based assistance in multiple Indian languages.

### 🎯 Key Highlights

- **Multi-lingual Voice Support**: Interact with the chatbot in multiple Indian languages using Sarvam AI.
- **Real-time Market Prices**: Get up-to-date agricultural commodity prices from AGMARKNET.
- **Crop Disease Detection**: AI-powered image classification using ResNet50 for plant disease identification.
- **Location-based Insights**: Personalized recommendations based on the farmer's location.
- **Offline Support**: Core features available without internet connectivity.

---

## ✨ Features

### 🎤 Voice-Enabled Chat
- Natural language processing for farmer queries.
- Speech-to-text and text-to-speech in regional languages.
- Context-aware conversation management.

### 💰 Market Price Intelligence
- Real-time commodity price tracking across Indian markets.
- Historical price trends and analysis.
- Location-specific market information.
- Price alerts and notifications.

### 🌿 Crop Disease Detection
- Image-based plant disease identification.
- Deep learning model with high accuracy.
- Treatment recommendations and preventive measures.
- Support for 10+ major crops.

### 🗺️ Location Services
- District-wise agricultural data.
- Weather information integration.
- Localized crop recommendations.

---

## 🏗️ Architecture

### Technology Stack

#### **Frontend**
- **Flutter**: Cross-platform mobile framework
- **Dart**: Primary programming language
- **Material Design**: UI components

#### **Backend**
- **FastAPI**: High-performance Python web framework
- **MongoDB**: NoSQL database for user and price data
- **PyTorch**: Deep learning framework for ML models
- **Sarvam AI**: Voice processing and translation

#### **Machine Learning**
- **Image Classifier**: ResNet50-based CNN for disease detection
- **Text Classifier**: Intent classification for user queries
- **Slot Filler**: Entity extraction from farmer conversations

### System Architecture
```
┌─────────────────┐
│  Flutter App    │
│  (Mobile UI)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  FastAPI Server │
│  (API Gateway)  │
└────────┬────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐ ┌──────────┐
│MongoDB │ │ML Models │
│Database│ │(PyTorch) │
└────────┘ └──────────┘
```

---

## 🚀 Installation

### Prerequisites

- Flutter SDK (v3.0+)
- Python (v3.11+)
- MongoDB (v6.0+)
- Git LFS (for model files)

### Frontend Setup


# Clone the repository
git clone https://github.com/Raakshass/DigiKisan.git
cd DigiKisan

# Install Flutter dependencies
flutter pub get

# Run the app
flutter run

Backend Setup
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Download ML models (if not using Git LFS)
python download_models.py

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Environment Configuration

Create a .env file in the backend/ directory:

MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=digikisan
SECRET_KEY=your-secret-key-here
SARVAM_API_KEY=your-sarvam-api-key
AGMARKNET_API_KEY=your-agmarknet-key

📱 Usage
For Farmers

Register/Login: Create an account or log in

Select Language: Choose your preferred language

Ask Questions: Use voice or text to ask about:

Market prices

Crop diseases

Weather updates

Agricultural practices

Take Photos: Snap pictures of crops for disease detection

View Results: Get instant AI-powered insights

For Developers
API Endpoints

Authentication

POST /api/auth/register - Register new user
POST /api/auth/login - User login


Chat

POST /api/chat/text - Text-based query
POST /api/chat/voice - Voice-based query


Price Data

GET /api/prices/commodity/{name} - Get commodity prices
GET /api/prices/location/{district} - Location-based prices


Image Classification

POST /api/classify/image - Crop disease detection

🧠 Machine Learning Models
Image Classifier

Architecture: ResNet50 (Transfer Learning)

Dataset: Custom agricultural disease dataset

Accuracy: 94.2% on test set

Classes: 10+ crop diseases

Size: 281 MB (stored via Git LFS)

Text Classifier

Model: Custom LSTM-based intent classifier

Features: Query intent detection (price, disease, weather, general)

Languages: Hindi, English, and regional languages

📊 Project Structure
```
DigiKisan/
├── lib/                      # Flutter app source
│   ├── core/                 # Core utilities
│   ├── presentation/         # UI screens
│   ├── services/             # API services
│   ├── widgets/              # Reusable widgets
│   └── main.dart             # App entry point
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── core/             # Config & database
│   │   ├── models/           # Data models
│   │   └── services/         # Business logic
│   ├── models/               # ML model files
│   └── requirements.txt      # Python dependencies
├── assets/                   # Images, fonts, icons
├── android/                  # Android native code
├── ios/                      # iOS native code
└── README.md                 # This file
```
🤝 Contributing

Contributions are welcome! Please follow these steps:

Fork the repository

Create a feature branch (git checkout -b feature/AmazingFeature)

Commit your changes (git commit -m 'Add some AmazingFeature')

Push to the branch (git push origin feature/AmazingFeature)

Open a Pull Request

📄 License

This project is licensed under the MIT License - see the LICENSE
 file for details.

👥 Team

Developer: Raakshass

🙏 Acknowledgments

Sarvam AI
 - Voice processing

AGMARKNET
 - Market data

Flutter
 - Mobile framework

FastAPI
 - Backend framework

📞 Contact

For questions, feedback, or support:

GitHub Issues: Create an issue

Email: siddhantjainofficial26@gmail.com

<div align="center">

Made with ❤️ for Indian Farmers

⭐ Star this repo if you find it useful!

</div>
