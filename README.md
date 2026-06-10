# 🌾 KisanMitra AI — AI-Powered Agricultural Intelligence Platform

[![CI](https://github.com/Raakshass/DigiKisan/actions/workflows/ci.yml/badge.svg)](https://github.com/Raakshass/DigiKisan/actions)

**KisanMitra AI** is a production-grade mobile platform that empowers Indian farmers with real-time crop price information, AI-driven disease diagnosis, and multilingual voice-enabled chat — all backed by a RAG-augmented knowledge base with state-specific contingency documents.

## 🏗️ Architecture

```
Flutter Mobile App (Dart)
├── Auth (Login/Register with JWT)
├── Chat Screen (Composable widgets)
│   ├── Text chat → RAG-augmented Gemini AI
│   ├── Voice input → Sarvam STT → English → AI → TTS
│   ├── Image upload → ResNet50 classifier → AI consultation
│   └── Price queries → Slot filling → Market data
└── 11-language support (Hindi, Tamil, Telugu, Bengali, etc.)

FastAPI Backend (Python)
├── 5 modular routers (chat, disease, auth, health, voice)
├── ChatOrchestrator (intent → RAG → Gemini → memory)
├── RAG Pipeline (ChromaDB + MiniLM embeddings)
│   ├── Static KB (7 agriculture docs, ~15K words)
│   └── Monthly ingestion (CRIDA contingency, weather, state advisories)
├── Firebase Integration (Cloud Storage + Firestore)
├── Async price scraper (4-tier fallback, no Selenium)
└── ResNet50 crop disease classifier (38 diseases)
```

## ⚡ Quick Start

### Backend
```bash
cd backend
cp .env.example .env    # Edit with your API keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Flutter App
```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api
```

### Docker
```bash
docker-compose up --build
```

## 🔑 Required API Keys

| Key | Where to get it | Purpose |
|-----|----------------|---------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Chatbot AI |
| `MONGODB_URI` | [mongodb.com/atlas](https://www.mongodb.com/atlas) | User auth, analytics |
| `SARVAM_API_KEY` | [sarvam.ai](https://dashboard.sarvam.ai) | Voice (STT/TTS/Translate) |

## 🧪 Testing

```bash
cd backend && pytest tests/ -v    # 35+ tests
flutter analyze                    # Dart static analysis
```

## 📱 Features

- **💬 AI Chat** — RAG-augmented agricultural advisor with location-aware contingency data
- **🎤 Voice** — Speak in Hindi/Tamil/Telugu → get voice responses back
- **📸 Disease Detection** — Upload crop photo → ResNet50 classification + AI consultation
- **💰 Market Prices** — Real-time mandi prices via data.gov.in + AgMarkNet
- **🔐 Auth** — JWT-based registration and login
- **📊 Analytics** — Firebase Analytics + Crashlytics
- **📍 Location-Aware** — State-specific contingency plans from ICAR-CRIDA (5 states)
- **🔄 Monthly Refresh** — Auto-updated knowledge base via government data sources

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter 3.27 + Dart |
| Backend | FastAPI + Python 3.11 |
| AI | Google Gemini 1.5 Flash |
| RAG | LangChain + ChromaDB + sentence-transformers |
| Data Pipeline | Firebase Cloud Storage + Firestore + APScheduler |
| Voice | Sarvam AI (11 Indian languages) |
| Disease | ResNet50 (PyTorch, 38 classes) |
| Database | MongoDB (Motor async driver) |
| Auth | JWT + bcrypt |
| CI/CD | GitHub Actions |

## 📂 Project Structure

```
kisanmitra-ai/
├── lib/                          # Flutter app
│   ├── main.dart                 # Firebase init + auth check
│   ├── presentation/             # Screens + widgets
│   ├── services/                 # API, Auth, Image, Translation, Analytics
│   └── core/                     # Theme, routes, utils
├── backend/                      # FastAPI backend
│   ├── app/
│   │   ├── api/routers/          # 5 modular route files
│   │   ├── services/
│   │   │   ├── data_ingestion/   # Monthly RAG data pipeline
│   │   │   │   ├── base_source.py
│   │   │   │   ├── crida_scraper.py
│   │   │   │   └── firebase_store.py
│   │   │   └── ...               # Business logic
│   │   └── core/                 # Config, DB, state mappings
│   ├── knowledge_base/           # 7+ agriculture docs for RAG
│   ├── tests/                    # 35+ pytest tests
│   └── requirements.txt
├── .github/workflows/ci.yml      # CI pipeline
├── Dockerfile + docker-compose   # Container deployment
└── railway.toml                  # Railway one-click deploy
```

## 📄 License

MIT
