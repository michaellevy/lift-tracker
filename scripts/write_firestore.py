"""
Import parsed lift entries into Firestore.

Usage:
    python3 write_firestore.py --uid YOUR_FIREBASE_UID [--write]

By default runs in dry-run mode. Pass --write to actually write to Firestore.

To find your UID: open the app in Chrome, open DevTools console, and run:
    firebase.auth().currentUser.uid
"""

import os, sys, json, csv, argparse
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.cloud import firestore

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/datastore",
]
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE  = os.path.join(os.path.dirname(__file__), "token_firestore.json")
CSV_PATH    = os.path.join(os.path.dirname(__file__), "entries.csv")
PROJECT_ID  = "lifts-tracker-2a4ce"


def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def load_entries_from_csv():
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found. Run import_preview.py first.")
        sys.exit(1)
    entries = []
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            entries.append(row)
    return entries


def build_firestore_doc(row):
    """Convert a CSV row to a Firestore document dict."""
    dt = datetime.strptime(row["date"], "%Y-%m-%d").replace(
        hour=12, tzinfo=timezone.utc
    )
    sets   = int(row["sets"])   if row["sets"]   else 1
    reps   = int(row["reps"])   if row["reps"]   else 1
    weight = float(row["weight"]) if row["weight"] else 0.0

    return {
        "lift":   row["lift_id"],
        "date":   dt,
        "sets":   [{"sets": sets, "reps": reps, "weight": weight}],
        "notes":  row["notes"],
        # Mark as imported so it can be identified/rolled back if needed
        "_imported": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid",   required=True, help="Your Firebase user UID")
    parser.add_argument("--write", action="store_true",
                        help="Actually write to Firestore (default: dry run)")
    args = parser.parse_args()

    entries = load_entries_from_csv()
    print(f"Loaded {len(entries)} entries from {CSV_PATH}")

    if not args.write:
        print("\n=== DRY RUN — no data written ===")
        print("Sample entries that would be written:")
        for row in entries[:5]:
            doc = build_firestore_doc(row)
            print(f"  {row['date']}  {row['lift_id']:30s}  "
                  f"{doc['sets'][0]['sets']}x{doc['sets'][0]['reps']}@{doc['sets'][0]['weight']}")
        print(f"  ... ({len(entries) - 5} more)")
        print("\nRe-run with --write to import.")
        return

    print("\nAuthenticating with Google...")
    creds = get_credentials()
    db = firestore.Client(project=PROJECT_ID, credentials=creds)

    collection = db.collection("users").document(args.uid).collection("entries")

    # Check for existing imported entries to avoid double-import
    existing = list(collection.where("_imported", "==", True).limit(1).stream())
    if existing:
        print(f"\nWARNING: Found existing _imported=True entries in Firestore.")
        print("This suggests a previous import ran. Continue? [y/N] ", end="")
        if input().strip().lower() != "y":
            print("Aborted.")
            return

    print(f"\nWriting {len(entries)} entries to users/{args.uid}/entries/ ...")
    written = 0
    batch = db.batch()
    for i, row in enumerate(entries):
        doc_ref = collection.document()
        batch.set(doc_ref, build_firestore_doc(row))
        written += 1
        # Firestore batches are limited to 500 operations
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {written}/{len(entries)} committed...")

    batch.commit()
    print(f"\nDone. {written} entries written to Firestore.")
    print("Refresh the app to see your history.")


if __name__ == "__main__":
    main()
