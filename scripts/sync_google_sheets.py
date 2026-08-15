"""Utility script for syncing data between local CSV and Google Sheets."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.services.google_sheets_service import GoogleSheetsService


def sync_local_to_sheets(
    local_csv_path: str,
    credentials_path: str,
    spreadsheet_id: str,
    clear_first: bool = False,
) -> None:
    """Sync local CSV data to Google Sheets."""
    local_path = Path(local_csv_path)
    if not local_path.exists():
        print(f"❌ Local CSV not found: {local_csv_path}")
        return

    print(f"📖 Reading local CSV: {local_csv_path}")
    rows_to_upload = []

    with local_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row and row.get("gesture"):  # Skip empty rows
                rows_to_upload.append(row)

    if not rows_to_upload:
        print("⚠️  No data found in local CSV")
        return

    print(f"🔗 Connecting to Google Sheets...")
    try:
        sheets = GoogleSheetsService(credentials_path, spreadsheet_id)
    except Exception as e:
        print(f"❌ Failed to connect to Google Sheets: {e}")
        return

    if clear_first:
        print("🗑️  Clearing existing data from Google Sheets...")
        sheets.clear_worksheet()

    print(f"📤 Uploading {len(rows_to_upload)} rows to Google Sheets...")
    uploaded = sheets.append_rows(rows_to_upload)
    print(f"✅ Successfully uploaded {uploaded} rows")


def sync_sheets_to_local(
    credentials_path: str,
    spreadsheet_id: str,
    local_csv_path: str,
    append: bool = False,
) -> None:
    """Sync Google Sheets data to local CSV."""
    print(f"🔗 Connecting to Google Sheets...")
    try:
        sheets = GoogleSheetsService(credentials_path, spreadsheet_id)
    except Exception as e:
        print(f"❌ Failed to connect to Google Sheets: {e}")
        return

    print(f"📥 Downloading data from Google Sheets...")
    rows = sheets.get_all_rows()

    if not rows:
        print("⚠️  No data found in Google Sheets")
        return

    local_path = Path(local_csv_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if append and local_path.exists():
        print(f"📝 Appending to existing CSV: {local_csv_path}")
        with local_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["gesture", "timestamp", "channels", "imu"])
            writer.writerows(rows)
    else:
        print(f"💾 Writing to CSV: {local_csv_path}")
        with local_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["gesture", "timestamp", "channels", "imu"])
            writer.writeheader()
            writer.writerows(rows)

    print(f"✅ Successfully downloaded {len(rows)} rows to {local_csv_path}")


def show_stats(credentials_path: str, spreadsheet_id: str) -> None:
    """Show statistics about the Google Sheet."""
    print(f"🔗 Connecting to Google Sheets...")
    try:
        sheets = GoogleSheetsService(credentials_path, spreadsheet_id)
    except Exception as e:
        print(f"❌ Failed to connect to Google Sheets: {e}")
        return

    rows = sheets.get_all_rows()
    row_count = len(rows)

    if row_count == 0:
        print("📊 Google Sheet is empty")
        return

    # Count by gesture
    gestures = {}
    for row in rows:
        gesture = row.get("gesture", "unknown")
        gestures[gesture] = gestures.get(gesture, 0) + 1

    print(f"\n📊 Google Sheets Statistics:")
    print(f"   Total rows: {row_count}")
    print(f"   Unique gestures: {len(gestures)}")
    print(f"\n   Breakdown by gesture:")
    for gesture, count in sorted(gestures.items(), key=lambda x: -x[1]):
        print(f"      {gesture}: {count} samples")


def main():
    parser = argparse.ArgumentParser(description="Sync data between local CSV and Google Sheets")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Sync to Google Sheets
    sync_to = subparsers.add_parser(
        "upload", help="Sync local CSV to Google Sheets"
    )
    sync_to.add_argument("--csv", required=True, help="Path to local CSV file")
    sync_to.add_argument("--credentials", required=True, help="Path to Google credentials JSON")
    sync_to.add_argument("--sheet-id", required=True, help="Google Sheets ID")
    sync_to.add_argument(
        "--clear", action="store_true", help="Clear existing data in Google Sheet first"
    )

    # Sync from Google Sheets
    sync_from = subparsers.add_parser(
        "download", help="Sync Google Sheets to local CSV"
    )
    sync_from.add_argument("--credentials", required=True, help="Path to Google credentials JSON")
    sync_from.add_argument("--sheet-id", required=True, help="Google Sheets ID")
    sync_from.add_argument("--csv", required=True, help="Path to local CSV file")
    sync_from.add_argument(
        "--append", action="store_true", help="Append to existing CSV instead of overwriting"
    )

    # Show stats
    stats = subparsers.add_parser("stats", help="Show Google Sheets statistics")
    stats.add_argument("--credentials", required=True, help="Path to Google credentials JSON")
    stats.add_argument("--sheet-id", required=True, help="Google Sheets ID")

    args = parser.parse_args()

    if args.command == "upload":
        sync_local_to_sheets(
            args.csv, args.credentials, args.sheet_id, clear_first=args.clear
        )
    elif args.command == "download":
        sync_sheets_to_local(args.credentials, args.sheet_id, args.csv, append=args.append)
    elif args.command == "stats":
        show_stats(args.credentials, args.sheet_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
