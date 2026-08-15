#!/usr/bin/env python
"""Quick test to verify all changes are working."""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("VERIFYING GOOGLE SHEETS INTEGRATION CHANGES")
print("=" * 60)

# Test 1: Import Google Sheets Service
print("\n1. Testing GoogleSheetsService import...")
try:
    from app.services.google_sheets_service import GoogleSheetsService
    print("   ✓ GoogleSheetsService imported successfully")
except ImportError as e:
    print(f"   ⚠ Import error: {e}")
    print("   (This is normal if google-auth libraries aren't installed yet)")

# Test 2: Import and check config
print("\n2. Testing config with Google Sheets settings...")
try:
    from app.config import get_config
    config = get_config()
    print(f"   ✓ Config loaded successfully")
    print(f"     - DATASET_PATH: {config.DATASET_PATH}")
    print(f"     - GOOGLE_CREDENTIALS_PATH: {config.GOOGLE_CREDENTIALS_PATH or 'Not set'}")
    print(f"     - GOOGLE_SPREADSHEET_ID: {config.GOOGLE_SPREADSHEET_ID or 'Not set'}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Check DatasetRecorder signature
print("\n3. Testing DatasetRecorder with Google Sheets support...")
try:
    from app.services.dataset_recorder import DatasetRecorder
    import inspect
    sig = inspect.signature(DatasetRecorder.__init__)
    params = list(sig.parameters.keys())
    print(f"   ✓ DatasetRecorder initialized")
    print(f"     Parameters: {params}")
    if 'google_credentials_path' in params:
        print(f"     ✓ Google Sheets parameters found")
    else:
        print(f"     ⚠ Google Sheets parameters not found")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 4: Check dataset_loader for Google Sheets support
print("\n4. Testing dataset_loader with Google Sheets support...")
try:
    from ml.dataset_loader import load_dataset_from_google_sheets
    print(f"   ✓ load_dataset_from_google_sheets found")
except ImportError:
    print(f"   ✗ load_dataset_from_google_sheets not found")

# Test 5: Check train_model for Google Sheets support
print("\n5. Testing train_model with Google Sheets support...")
try:
    from ml.train_model import train_and_save
    import inspect
    sig = inspect.signature(train_and_save)
    params = list(sig.parameters.keys())
    print(f"   ✓ train_and_save found")
    if 'google_credentials_path' in params:
        print(f"     ✓ Google Sheets parameters found")
    else:
        print(f"     ⚠ Google Sheets parameters not found")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 6: Check ML service
print("\n6. Testing MLService with Google Sheets support...")
try:
    from app.services.ml_service import MLService
    import inspect
    sig = inspect.signature(MLService.retrain)
    params = list(sig.parameters.keys())
    print(f"   ✓ MLService.retrain found")
    if 'google_credentials_path' in params:
        print(f"     ✓ Google Sheets parameters found")
    else:
        print(f"     ⚠ Google Sheets parameters not found")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 7: Check if sync script exists
print("\n7. Testing sync script...")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("sync", "scripts/sync_google_sheets.py")
    if spec is not None:
        print(f"   ✓ sync_google_sheets.py found")
    else:
        print(f"   ✗ sync_google_sheets.py not found")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 8: Check documentation files
print("\n8. Checking documentation files...")
from pathlib import Path
docs = [
    "GOOGLE_SHEETS_SETUP.md",
    "RENDER_DEPLOYMENT.md",
    "CHANGES_SUMMARY.md",
    "QUICK_REFERENCE.md",
    ".env.example"
]
for doc in docs:
    path = Path(doc)
    if path.exists():
        size_kb = path.stat().st_size / 1024
        print(f"   ✓ {doc} ({size_kb:.1f} KB)")
    else:
        print(f"   ✗ {doc} not found")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
print("\nNext steps:")
print("1. Install Google dependencies: pip install -r requirements.txt")
print("2. Set up Google Sheets: See GOOGLE_SHEETS_SETUP.md")
print("3. Configure .env with credentials")
print("4. Test with: python -m app")
print("=" * 60)
