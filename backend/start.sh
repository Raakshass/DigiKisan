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

# --- Model Checkpoint Verification ---
MODEL_PATH="/app/models/image_classifier/best_model.pth"
if [ -f "$MODEL_PATH" ]; then
    MODEL_SIZE=$(stat -f%z "$MODEL_PATH" 2>/dev/null || stat -c%s "$MODEL_PATH" 2>/dev/null || echo "0")
    echo "[start.sh] Model checkpoint size: $MODEL_SIZE bytes"
    if [ "$MODEL_SIZE" -lt 10000 ]; then
        echo "[start.sh] WARNING: Model appears to be an LFS pointer ($MODEL_SIZE bytes). Attempting git lfs pull..."
        if command -v git &> /dev/null; then
            cd /app && git lfs install --skip-repo 2>/dev/null && git lfs pull 2>/dev/null
            NEW_SIZE=$(stat -f%z "$MODEL_PATH" 2>/dev/null || stat -c%s "$MODEL_PATH" 2>/dev/null || echo "0")
            echo "[start.sh] After git lfs pull: $NEW_SIZE bytes"
        else
            echo "[start.sh] git not available. Disease classifier will use fallback mode."
        fi
    else
        echo "[start.sh] Model checkpoint OK ($(($MODEL_SIZE / 1048576)) MB)"
    fi
else
    echo "[start.sh] WARNING: Model checkpoint not found at $MODEL_PATH"
fi

echo "[start.sh] Starting uvicorn on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
