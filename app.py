import os
import json
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/etc/secrets/service_account.json"
SPREADSHEET_ID = "1thZnhvqC_rZZH4Ixa7a2PoXnuq8gnWXBJGxsqjUk3KU"
SHEET_NAME = "Agent"
HEADER_ROW_INDEX = 1  # data starts at row 2

def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def score_lead(row):
    score = 0

    services = row.get("Company Services", "").lower()
    value_prop = row.get("Value Prop / Why a good fit", "").lower()
    size = row.get("CompanySize", "").lower()
    revenue = row.get("Annual Revenue", "").lower()
    notes = row.get("Notes", "").lower()

    # High-priority traits
    if any(kw in services for kw in ["outdoor", "sustainab", "adventure", "creative"]):
        score += 25
    if "photograph" in value_prop:
        score += 15
    if "campaign" in value_prop or "story" in value_prop:
        score += 15
    if "worked with photographers" in notes or "has photographer" in notes:
        score += 15
    if any(kw in size for kw in ["mid", "50", "100"]) or any(kw in revenue for kw in ["500k", "1m", "2m"]):
        score += 10
    if "marketing" in services or "brand" in services:
        score += 10

    # Penalties
    if any(kw in value_prop for kw in ["no marketing", "local org", "unclear"]):
        score -= 20
    if any(kw in services for kw in ["law", "fintech", "mlm", "coach", "realtor"]):
        score = 0

    return max(0, min(100, score))

@app.route("/")
def home():
    return jsonify({"message": "✅ Lead Enrichment API is running."})

@app.route("/enrich", methods=["POST"])
def enrich():
    try:
        sheet = get_sheet()
        headers = sheet.row_values(HEADER_ROW_INDEX)
        records = sheet.get_all_records(head=HEADER_ROW_INDEX)
        updated_count = 0

        for i, row in enumerate(records):
            row_num = i + 2
            if str(row.get("Enriched leads: 0", "")).strip() == "1":
                continue

            print(f"🔍 Enriching row {row_num}: {row.get('Company Name', '')}")

            score = score_lead(row)

            # Highlight current row yellow
            sheet.format(f"A{row_num}:P{row_num}", {"backgroundColor": {"red": 1, "green": 1, "blue": 0}})

            # Update Lead Score + Enrichment status
            sheet.update_cell(row_num, headers.index("Lead Score (1-100)") + 1, score)
            sheet.update_cell(row_num, headers.index("Enriched leads: 0") + 1, "1")
            sheet.update_cell(row_num, headers.index("Notes") + 1, row.get("Notes", "") + f" | Scored {score}")

            updated_count += 1

        return jsonify({"status": "done", "updated_rows": updated_count})
    
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
