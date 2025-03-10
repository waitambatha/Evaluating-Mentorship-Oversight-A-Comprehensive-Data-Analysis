import os
import requests
import json
import time
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ODK Central details
ODK_SERVER = os.getenv("ODK_DOMAIN", "https://odk.nmcp.or.ke/")
USERNAME = os.getenv("ODK_EMAIL")
PASSWORD = os.getenv("ODK_PASSWORD")
PROJECT_ID = os.getenv("PROJECT_ID", "36")
FORM_ID = os.getenv("FORM_ID", "FORM-1-Questionnaire-Evaluating-Mentorship-Oversight")

# Debugging: Ensure environment variables are loaded correctly
if not USERNAME or not PASSWORD:

    st.error("Missing ODK_EMAIL or ODK_PASSWORD. Check your .env file.")

# Token storage file
TOKEN_FILE = "odk_token.json"
OUTPUT_DIR = "odk_submissions"
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_FILE = f"{OUTPUT_DIR}/{FORM_ID}_submissions.csv"

def get_odk_token():
    """Generate and return a new ODK token, storing it with expiry."""
    url = f"{ODK_SERVER}/v1/sessions"
    headers = {"Content-Type": "application/json"}
    data = {"email": USERNAME, "password": PASSWORD}

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        token = token_data.get("token")
        expiry = time.time() + 3600  # Assume 1-hour token validity
        
        # Store token in JSON file
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token, "expiry": expiry}, f)
        return token
    else:
        st.error(f"Failed to get token: {response.text}")
        return None

def load_token():
    """Load a valid token or generate a new one if expired."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        if time.time() < token_data.get("expiry", 0):
            return token_data["token"]
    return get_odk_token()

def download_csv():
    """Download submissions as a CSV file using a valid token."""
    token = load_token()
    url = f"{ODK_SERVER}/v1/projects/{PROJECT_ID}/forms/{FORM_ID}/submissions.csv"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 401:
            # Token expired, regenerate and retry
            token = get_odk_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=headers)
        response.raise_for_status()
        with open(CSV_FILE, "wb") as f:
            f.write(response.content)
        st.success(f"CSV successfully downloaded to {CSV_FILE}")
    except requests.RequestException as e:
        st.error(f"Failed to download CSV: {e}")

@st.cache_data(ttl=1800)
def load_data():
    """Load the CSV data, ensuring it's downloaded first."""
    download_csv()
    if os.path.exists(CSV_FILE):
        try:
            return pd.read_csv(CSV_FILE)
        except Exception as e:
            st.error(f"Error reading CSV file: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# ----------------- Streamlit App Interface -----------------
st.title("Evaluating Mentorship Oversight: A Comprehensive Data Analysis")

if st.button("Download Latest CSV"):
    download_csv()

data = load_data()

if data.empty:
    st.warning("No data available. Click the button above to fetch the latest CSV.")
else:
    st.header("Tables")
    st.subheader("Full Data")
    st.dataframe(data, height=300)
