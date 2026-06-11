#!/bin/bash
# ==============================================================================
# KisanMitra AI Backend — Startup Script
# ==============================================================================
# Handles:
# 1. Decoding FIREBASE_SA_BASE64 env var into firebase-sa.json (for HF Spaces)
# 2. Starting uvicorn on the correct port
# ==============================================================================

set -e

# --- Firebase Service Account ---
# On HF Spaces, we store the Firebase SA key as a base64-encoded secret.
# Decode it into a JSON file at runtime so firebase-admin can use it.
if [ -n "$FIREBASE_SA_BASE64" ]; then
    echo "$FIREBASE_SA_BASE64" | base64 -d > /app/firebase-sa.json
    export GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-sa.json
    echo "[start.sh] Firebase SA decoded from env var"
elif [ -f /app/firebase-sa.json ]; then
    export GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-sa.json
    echo "[start.sh] Using existing firebase-sa.json file"
else
    echo "[start.sh] WARNING: No Firebase credentials found. Firestore will be unavailable."
fi

# --- Start Uvicorn ---
PORT="${PORT:-7860}"
echo "[start.sh] Starting uvicorn on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
