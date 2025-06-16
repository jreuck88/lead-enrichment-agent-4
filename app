import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google Sheets config
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "service_account.json"  # Mounted via Render secret
SPREADSHEET_ID = "1thZnhvqC_rZZH4Ixa7a2PoXnuq8gnWXBJGxsqjUk3KU"
SHEET_NAME = "Agent"
HEADER_ROW_INDEX = 1  # Headers are in row 1

def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def enrich_row(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional research assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json") or content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        return {"error": str(e)}

@app.route("/")
def home():
    return jsonify({"status": "✅ Lead Enrichment API running (v4)"})

@app.route("/enrich", methods=["POST"])
def enrich():
    try:
        sheet = get_sheet()
        headers = sheet.row_values(HEADER_ROW_INDEX)
        records = sheet.get_all_records(head=HEADER_ROW_INDEX)
        updated = 0

        for i, row in enumerate(records):
            row_num = i + 2  # row 2 is where data starts
            if str(row.get("Enriched", "")).strip() == "1":
                continue

            prompt = f"""Enrich this company:
Company: {row.get("Company Name")}
Location: {row.get("Location")}
Website: {row.get("Website")}

Return JSON with these keys:
Company Name, Company Email, Location, Best Point of Contact (POC) and their Role, Individual POC info / email, Individual POC LinkedIn URL, Company Instagram URL, Company LinkedIn URL, Website, Company Services, Value Prop / Why a good fit, Company size (# of employees), Annual Revenue, Lead Score (1-100)
"""

            enriched = enrich_row(prompt)
            if "error" in enriched:
                continue

            for key, val in enriched.items():
                if key in headers:
                    col_index = headers.index(key) + 1
                    sheet.update_cell(row_num, col_index, val)

            sheet.update_cell(row_num, headers.index("Enriched") + 1, "1")
            sheet.update_cell(row_num, headers.index("Date Added") + 1, datetime.now().strftime("%Y-%m-%d"))
            updated += 1

        return jsonify({"updated": updated})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
