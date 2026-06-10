"""Quick Firebase connectivity test — delete after use."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
print(f"Firebase enabled: {settings.firebase_enabled}")
print(f"Service account: {settings.firebase_service_account}")
print(f"Storage bucket: {settings.firebase_storage_bucket}")
print(f"Target states: {settings.target_states_list}")
print(f"MongoDB dbname: {settings.mongodb_dbname}")
print()

from app.services.data_ingestion.firebase_store import get_firebase_store
store = get_firebase_store()
print(f"Firebase active: {store.is_firebase_active}")

if store.is_firebase_active:
    print("\n--- Testing Firestore write ---")
    import asyncio
    async def test_write():
        result = await store.upload_document(
            content="# Test Document\nThis is a connectivity test.",
            state="UP",
            district="Lucknow",
            source_name="test",
            category="test",
            filename="connectivity_test.md",
            metadata={"test": True},
        )
        print(f"Upload result: {result}")
        # Clean up
        if result.get("ok"):
            print("✅ Firebase read/write verified!")
    asyncio.run(test_write())
else:
    print("⚠️ Firebase not active — check .env values")
