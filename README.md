# KisanMitra AI - Agricultural Intelligence Platform

[![CI](https://github.com/Raakshass/DigiKisan/actions/workflows/ci.yml/badge.svg)](https://github.com/Raakshass/DigiKisan/actions)

KisanMitra AI is a production-grade mobile platform designed to empower Indian farmers with real-time crop price information, AI-driven disease diagnosis, and multilingual voice-enabled chat. The platform is backed by a RAG-augmented knowledge base that includes state-specific contingency documents and automated data ingestion pipelines.

## Architecture

```mermaid
graph TD
    subgraph Mobile Client [Flutter Mobile App]
        UI[UI Components]
        Auth[Firebase Auth]
        Voice[Sarvam STT/TTS]
        Cam[Camera / Image Upload]
        
        UI --> Auth
        UI --> Voice
        UI --> Cam
    end

    subgraph Backend Services [FastAPI Backend]
        API[API Router Gateway]
        Orchestrator[Chat Orchestrator]
        RAG[RAG Pipeline / ChromaDB]
        CV[ResNet50 Classifier]
        Prices[Price Scraper]
        
        API --> Orchestrator
        Orchestrator --> RAG
        API --> CV
        API --> Prices
    end

    subgraph Data Sources [External Integrations]
        LLM[OpenRouter / Gemini AI]
        AgMarkNet[AgMarkNet & Data.gov.in]
        CRIDA[ICAR-CRIDA Contingency DB]
        Weather[Open-Meteo]
    end

    subgraph Cloud Infrastructure [Firebase & Render]
        Firestore[(Firestore Database)]
        Storage[(Firebase Storage)]
    end

    Mobile Client -- REST APIs --> API
    Mobile Client -- ID Token --> API
    Auth --> Firestore
    
    Orchestrator --> LLM
    Prices --> AgMarkNet
    Prices --> Firestore
    
    RAG --> CRIDA
    RAG --> Weather
    
    CV --> Storage
```

## Features and Integrations

### 1. Multilingual AI Assistant (RAG)
The core of KisanMitra is an LLM-powered chatbot orchestrated via OpenRouter. To ensure agricultural accuracy, the AI is augmented with a Retrieval-Augmented Generation (RAG) pipeline utilizing ChromaDB and MiniLM embeddings.

### 2. Automated Data Ingestion (Web Scraping)
We scrape and ingest data from multiple government and open-source platforms to keep the knowledge base and pricing engine up to date:
*   **AgMarkNet / Data.gov.in**: Real-time agricultural market prices (mandi prices) across India. We use an asynchronous, 4-tier fallback scraper (no Selenium required).
*   **ICAR-CRIDA**: State-specific agricultural contingency plans and advisories.
*   **Open-Meteo**: High-resolution weather forecasting APIs.

### 3. Crop Disease Diagnostics
Farmers can upload images of diseased crops directly from their mobile cameras. The backend runs a ResNet50 Convolutional Neural Network (PyTorch) fine-tuned on 38 distinct crop disease classes to provide immediate diagnoses and treatment recommendations.

### 4. Voice Processing
To maintain accessibility for farmers across India, the app integrates **Sarvam AI** for local language voice processing. Farmers can speak in Hindi, Tamil, Telugu, and Bengali, which is processed via Speech-to-Text (STT), passed to the AI engine, and returned via Text-to-Speech (TTS).

### 5. Infrastructure
*   **Authentication & Database**: Firebase Auth provides secure, client-side authentication. Session management, price caching, and query analytics are persisted in Firebase Firestore.
*   **Deployment**: The FastAPI backend is containerized via Docker and deployed on Render (Singapore region) for low-latency access.

## Quick Start

### Backend Setup

```bash
cd backend
cp .env.example .env    # Edit with your API keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Flutter App Setup

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api
```

### Docker Deployment

```bash
docker-compose up --build
```

## Required Environment Variables

| Variable | Source | Purpose |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai/) | Primary LLM gateway |
| `SARVAM_API_KEY` | [Sarvam AI](https://dashboard.sarvam.ai) | Voice translation (STT/TTS) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Console | Path to `firebase-sa.json` for Firestore |

## Project Structure

```text
kisanmitra-ai/
├── lib/                          # Flutter application
│   ├── main.dart                 # Firebase initialization
│   ├── presentation/             # UI screens and widgets
│   ├── services/                 # API, Auth, and Analytics clients
│   └── core/                     # Theming and routing
├── backend/                      # FastAPI Python backend
│   ├── app/
│   │   ├── api/routers/          # Modular API endpoints
│   │   ├── services/             # Business logic (RAG, CV, Scraper)
│   │   │   └── data_ingestion/   # Integration with CRIDA and Open-Meteo
│   │   └── core/                 # App configuration
│   ├── knowledge_base/           # Static agriculture documents for RAG
│   ├── tests/                    # Pytest suite
│   ├── Dockerfile                # Container definition
│   └── requirements.txt          # Python dependencies
├── render.yaml                   # Render deployment configuration
└── .github/workflows/ci.yml      # CI/CD pipeline definition
```

## License

MIT License
