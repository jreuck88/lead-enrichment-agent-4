from flask import Flask, jsonify, request
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import re

# Load .env vars
load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Config
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/etc/secrets/service_account.json"  # ✅ Updated path
SPREADSHEET_ID = "1thZnhvqC_rZZH4Ixa7a2PoXnuq8gnwXBJGxsqjUk3KU"
SHEET_NAME = "Agent"
HEADER_ROW_INDEX = 1  # row 1 = headers, data starts at row 2

# Utilities
def get_sheet():
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"🔒 Missing credentials file: {CREDS_FILE}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def parse_company_data(row):
    return {
        "company": row[0],
        "website": row[8] if len(row) > 8 else "",
        "services": row[9] if len(row) > 9 else "",
        "value_prop": row[10] if len(row) > 10 else "",
        "notes": row[11] if len(row) > 11 else "",
    }

def score_lead(data):
    text = " ".join(data.values()).lower()
    score = 0
    if re.search(r"outdoor|sustainab|adventure|creative\sagency", text):
        score += 30
    if re.search(r"photographer|photo|visual|imagery", text):
        score += 20
    if re.search(r"marketing|social\smedia|campaign", text):
        score += 20
    if re.search(r"budget|custom\sphotography|professional", text):
        score += 20
    if re.search(r"mid-size|growing|agency", text):
        score += 10
    return min(score, 100)

# Routes
@app.route("/")
def index():
    return "✅ Lead Enrichment Agent is alive"

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "timestamp": str(datetime.utcnow())})

@app.route("/debug-secrets")
def debug_secrets():
    try:
        files = os.listdir("/etc/secrets")
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/enrich", methods=["POST"])
def enrich():
    try:
        sheet = get_sheet()
        headers = sheet.row_values(HEADER_ROW_INDEX)
        rows = sheet.get_all_values()[HEADER_ROW_INDEX:]

        for idx, row in enumerate(rows, start=HEADER_ROW_INDEX + 1):
            try:
                if not row or len(row) < 16 or row[15].strip():
                    continue

                # Highlight active row yellow
                sheet.format(f"A{idx}:P{idx}", {"backgroundColor": {"red": 1, "green": 1, "blue": 0}})

                company = parse_company_data(row)
                score = score_lead(company)

                sheet.update_cell(idx, 16, str(score))  # col P
                sheet.update_cell(idx, 17, "1")         # col Q
            except Exception as row_err:
                sheet.update_cell(idx, 17, f"error: {row_err}")
                continue

        return jsonify({"status": "success", "timestamp": str(datetime.utcnow())})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
