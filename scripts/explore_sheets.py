"""
Explore the Google Sheets lifting history workbook.
Reads all YYYY-MM sheets and prints their content so we can understand the format.

Usage:
    python3 explore_sheets.py

Requires credentials.json in the same directory (see README in this folder).
"""

import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID = "1BpjoT3mXofJem4JMQtbbi3c8O35ftRAQ4ley2zSgcEQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def get_service():
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
    return build("sheets", "v4", credentials=creds)


def is_date_sheet(title):
    """Return True if the sheet title looks like YYYY-MM."""
    import re
    return bool(re.match(r"^\d{4}-\d{2}$", title.strip()))


def main():
    service = get_service()
    ss = service.spreadsheets()

    # Get all sheet names
    meta = ss.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = meta["sheets"]
    print(f"All sheets ({len(sheets)} total):")
    for s in sheets:
        print(f"  {'*' if is_date_sheet(s['properties']['title']) else ' '} {s['properties']['title']}")

    print("\n" + "="*80)
    date_sheets = [s for s in sheets if is_date_sheet(s["properties"]["title"])]
    print(f"\nFound {len(date_sheets)} date sheets: {[s['properties']['title'] for s in date_sheets]}")

    for sheet in date_sheets:
        title = sheet["properties"]["title"]
        print(f"\n{'='*80}")
        print(f"SHEET: {title}")
        print("="*80)

        result = ss.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{title}'",
            valueRenderOption="FORMATTED_VALUE"
        ).execute()

        rows = result.get("values", [])
        if not rows:
            print("  (empty)")
            continue

        # Print as a simple grid with column indices
        print(f"  Rows: {len(rows)}, Max cols: {max(len(r) for r in rows)}")
        print()

        # Print header row indices
        max_cols = max(len(r) for r in rows)
        col_header = "     " + "".join(f"{i:<20}" for i in range(max_cols))
        print(col_header)
        print("     " + "-" * (max_cols * 20))

        for row_i, row in enumerate(rows):
            # Pad row to max_cols
            padded = row + [""] * (max_cols - len(row))
            row_str = f"{row_i:<4} " + "".join(f"{str(cell)[:19]:<20}" for cell in padded)
            print(row_str)


if __name__ == "__main__":
    main()
