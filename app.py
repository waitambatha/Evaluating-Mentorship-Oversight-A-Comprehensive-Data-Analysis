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
ODK_SERVER = os.getenv("ODK_DOMAIN")
USERNAME = os.getenv("ODK_EMAIL")
PASSWORD = os.getenv("ODK_PASSWORD")
PROJECT_ID = os.getenv("PROJECT_ID")
FORM_ID = os.getenv("FORM_ID")

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

    # Summary Table
    st.subheader("Summary")
    numeric_cols = data.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        summary = data[numeric_cols].describe().T.reset_index().rename(columns={"index": "Column"})
    else:
        summary = pd.DataFrame({"Metric": ["Total Submissions"], "Value": [data.shape[0]]})
    st.dataframe(summary, height=300)

    # ----------------- Interactive Charts -----------------
    st.header("Interactive Charts")

    # Bar Chart
    st.subheader("Bar Chart")
    if numeric_cols:
        selected_bar = st.selectbox("Select a numeric column for Bar Chart", numeric_cols, key="bar")
        bar_data = data[selected_bar].value_counts().reset_index()
        bar_data.columns = [selected_bar, "Count"]
        fig_bar = px.bar(bar_data, x=selected_bar, y="Count", title=f"Bar Chart of {selected_bar}")
        st.plotly_chart(fig_bar)

    # Line Chart
    st.subheader("Line Chart")
    if "submission_date" in data.columns:
        data["submission_date"] = pd.to_datetime(data["submission_date"], errors="coerce")
        line_data = data.groupby(data["submission_date"].dt.date).size().reset_index(name="Submissions")
        fig_line = px.line(line_data, x="submission_date", y="Submissions", title="Submissions Over Time")
        st.plotly_chart(fig_line)

    # Pie Chart
    st.subheader("Pie Chart")
    categorical_cols = data.select_dtypes(include="object").columns.tolist()
    if categorical_cols:
        selected_pie = st.selectbox("Select a categorical column for Pie Chart", categorical_cols, key="pie")
        pie_data = data[selected_pie].value_counts().reset_index()
        pie_data.columns = [selected_pie, "Count"]
        fig_pie = px.pie(pie_data, names=selected_pie, values="Count", title=f"Pie Chart of {selected_pie}")
        st.plotly_chart(fig_pie)
