"""
Dump all YYYY-MM sheets as JSON files for analysis.
"""
import os, json, re
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

def main():
    service = get_service()
    ss = service.spreadsheets()
    meta = ss.get(spreadsheetId=SPREADSHEET_ID).execute()

    for sheet in meta["sheets"]:
        title = sheet["properties"]["title"]
        if not re.match(r"^\d{4}-\d{2}(-\d{2})?$", title.strip()):
            continue
        result = ss.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{title}'",
            valueRenderOption="FORMATTED_VALUE"
        ).execute()
        rows = result.get("values", [])
        out = os.path.join(os.path.dirname(__file__), f"sheet_{title}.json")
        with open(out, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"Saved {title}: {len(rows)} rows -> {out}")

if __name__ == "__main__":
    main()
