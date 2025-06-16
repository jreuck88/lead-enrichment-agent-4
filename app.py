from flask import Flask, jsonify
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import re

load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/etc/secrets/service_account.json"
SPREADSHEET_ID = "1thZnhvqC_rZZH4Ixa7a2PoXnuq8gnwXBJGxsqjUk3KU"
SHEET_NAME = "Agent"
HEADER_ROW_INDEX = 1  # Header is in row 1; data starts row 2

def get_sheet():
    print("📂 Debug: Listing /etc/secrets contents...")
    try:
        print(os.listdir("/etc/secrets"))
    except Exception as e:
        print(f"❌ Could not list /etc/secrets: {e}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def parse_company_data(row):
    return {
        "company": row[0],
        "website": row[8],
        "services": row[9],
        "value_prop": row[10],
        "notes": row[11],
    }

def score_lead(company_data):
    notes = " ".join(company_data.values()).lower()
    score = 0
    if re.search(r"outdoor|sustainab|adventure|creative\sagency", notes):
        score += 30
    if re.search(r"photographer|photo|visual|imagery", notes):
        score += 20
    if re.search(r"marketing|social\smedia|campaign", notes):
        score += 20
    if re.search(r"budget|custom\sphotography|professional", notes):
        score += 20
    if re.search(r"mid-size|growing|agency", notes):
        score += 10
    return min(score, 100)

@app.route("/")
def index():
    return "✅ Lead Enrichment Agent is running"

@app.route("/enrich", methods=["GET", "POST"])
def enrich():
    sheet = get_sheet()
    rows = sheet.get_all_values()[HEADER_ROW_INDEX:]
    headers = sheet.row_values(HEADER_ROW_INDEX)

    for idx, row in enumerate(rows, start=HEADER_ROW_INDEX + 1):
        try:
            if not row or len(row) < 16 or row[15].strip():
                continue  # Already enriched

            sheet.format(f"A{idx}:P{idx}", {"backgroundColor": {"red": 1, "green": 1, "blue": 0}})  # highlight yellow

            company_data = parse_company_data(row)
            score = score_lead(company_data)

            sheet.update_cell(idx, 16, str(score))  # column P: Lead Score (1–100)
            sheet.update_cell(idx, 17, "1")         # column Q: Enriched leads
        except Exception as e:
            sheet.update_cell(idx, 17, f"error: {e}")
            continue

    return jsonify({"status": "success", "timestamp": str(datetime.utcnow())})

@app.route("/debug-secrets")
def debug_secrets():
    try:
        files = os.listdir("/etc/secrets")
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)
