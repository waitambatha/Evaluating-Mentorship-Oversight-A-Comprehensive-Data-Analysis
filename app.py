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

# Summary at the top
st.header("Summary Overview")
if data.empty:
    st.write("No data loaded yet. Please download the latest CSV to see the summary.")
else:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Submissions", data.shape[0])
    with col2:
        numeric_cols = data.select_dtypes(include="number").columns.tolist()
        st.metric("Numeric Columns", len(numeric_cols))
    with col3:
        categorical_cols = data.select_dtypes(include="object").columns.tolist()
        st.metric("Categorical Columns", len(categorical_cols))
    if "submission_date" in data.columns:
        try:
            data["submission_date"] = pd.to_datetime(data["submission_date"], errors="coerce")
            date_range = f"{data['submission_date'].min().date()} to {data['submission_date'].max().date()}"
            st.write(f"Date Range: {date_range}")
        except Exception:
            st.write("Date Range: Not available")

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
    if numeric_cols:
        summary = data[numeric_cols].describe().T.reset_index().rename(columns={"index": "Column"})
    else:
        summary = pd.DataFrame({"Metric": ["Total Submissions"], "Value": [data.shape[0]]})
    st.dataframe(summary, height=300)

    # ----------------- Interactive Charts -----------------
    st.header("Interactive Charts")

    # 1. Bar Chart: Distribution for a selected numeric column
    st.subheader("Bar Chart")
    if numeric_cols:
        selected_bar = st.selectbox("Select a numeric column for Bar Chart", numeric_cols, key="bar")
        bar_data = data[selected_bar].value_counts().reset_index()
        bar_data.columns = [selected_bar, "Count"]
        fig_bar = px.bar(bar_data, x=selected_bar, y="Count", title=f"Bar Chart of {selected_bar}")
        st.plotly_chart(fig_bar)

    # 2. Line Chart: Trend over time if a date column exists
    st.subheader("Line Chart")
    if "submission_date" in data.columns:
        try:
            data["submission_date"] = pd.to_datetime(data["submission_date"], errors="coerce")
            line_data = data.groupby(data["submission_date"].dt.date).size().reset_index(name="Submissions")
            fig_line = px.line(line_data, x="submission_date", y="Submissions", title="Submissions Over Time")
            st.plotly_chart(fig_line)
        except Exception as e:
            st.error(f"Error processing 'submission_date' column: {e}")

    # 3. Pie Chart: Distribution for a selected categorical column
    st.subheader("Pie Chart")
    categorical_cols = data.select_dtypes(include="object").columns.tolist()
    if categorical_cols:
        selected_pie = st.selectbox("Select a categorical column for Pie Chart", categorical_cols, key="pie")
        pie_data = data[selected_pie].value_counts().reset_index()
        pie_data.columns = [selected_pie, "Count"]
        fig_pie = px.pie(pie_data, names=selected_pie, values="Count", title=f"Pie Chart of {selected_pie}")
        st.plotly_chart(fig_pie)

    # 4. Histogram: User selects an x-axis column and a y-axis column for aggregation
    st.subheader("Histogram")
    if numeric_cols:
        selected_hist_x = st.selectbox("Select X-axis for Histogram", numeric_cols, key="hist_x")
        selected_hist_y = st.selectbox("Select Y-axis for Histogram (Aggregation)", ["None"] + numeric_cols,
                                       key="hist_y")
        if selected_hist_y == "None":
            fig_hist = px.histogram(data, x=selected_hist_x, title=f"Histogram of {selected_hist_x}")
        else:
            fig_hist = px.histogram(
                data, x=selected_hist_x, y=selected_hist_y, histfunc="sum",
                title=f"Histogram of {selected_hist_x} aggregated by {selected_hist_y}"
            )
        st.plotly_chart(fig_hist)

    # 5. Scatter Plot: Relationship between two numeric columns
    st.subheader("Scatter Plot")
    if len(numeric_cols) >= 2:
        scatter_x = st.selectbox("Select X-axis for Scatter Plot", numeric_cols, key="scatter_x")
        scatter_y = st.selectbox("Select Y-axis for Scatter Plot", numeric_cols, key="scatter_y")
        fig_scatter = px.scatter(data, x=scatter_x, y=scatter_y, title=f"Scatter Plot: {scatter_x} vs {scatter_y}")
        st.plotly_chart(fig_scatter)

    # 6. Box Plot: Distribution summary of a selected numeric column
    st.subheader("Box Plot")
    if numeric_cols:
        selected_box = st.selectbox("Select a numeric column for Box Plot", numeric_cols, key="box")
        fig_box = px.box(data, y=selected_box, title=f"Box Plot of {selected_box}")
        st.plotly_chart(fig_box)

    # 7. Correlation Heatmap: Shows correlations among numeric columns
    st.subheader("Correlation Heatmap")
    if len(numeric_cols) >= 2:
        corr = data[numeric_cols].corr()
        fig_heat = px.imshow(corr, text_auto=True, aspect="auto", title="Correlation Heatmap")
        st.plotly_chart(fig_heat)

    # 8. Violin Plot: Distribution for a selected numeric column with optional grouping
    st.subheader("Violin Plot")
    if numeric_cols:
        selected_violin = st.selectbox("Select a numeric column for Violin Plot", numeric_cols, key="violin")
        if categorical_cols:
            group_by = st.selectbox("Group by (optional)", ["None"] + categorical_cols, key="violin_group")
            if group_by == "None":
                fig_violin = px.violin(data, y=selected_violin, box=True, points="all",
                                       title=f"Violin Plot of {selected_violin}")
            else:
                fig_violin = px.violin(data, y=selected_violin, color=group_by, box=True, points="all",
                                       title=f"Violin Plot of {selected_violin} grouped by {group_by}")
        else:
            fig_violin = px.violin(data, y=selected_violin, box=True, points="all",
                                   title=f"Violin Plot of {selected_violin}")
        st.plotly_chart(fig_violin)
