import requests
import os
import time
import schedule
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ODK Central details from .env file
ODK_SERVER = os.getenv("ODK_DOMAIN")
USERNAME = os.getenv("ODK_EMAIL")
PASSWORD = os.getenv("ODK_PASSWORD")
PROJECT_ID = os.getenv("PROJECT_ID")  # Example: 1
FORM_ID = os.getenv("FORM_ID")  # Example: "example_form"

# Directory to save CSV files
OUTPUT_DIR = "odk_submissions"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_odk_token():
    """Authenticate with ODK Central and retrieve an API token."""
    url = f"{ODK_SERVER}/v1/sessions"
    data = {"email": USERNAME, "password": PASSWORD}
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise error if request fails
        token = response.json().get("token")
        return token
    except requests.RequestException as e:
        print(f"Error obtaining ODK token: {e}")
        return None

def download_csv():
    """Download ODK submissions as a CSV file."""
    token = get_odk_token()
    print(token)
    if not token:
        print("❌ Could not authenticate. Skipping CSV download.")
        return
    
    url = f"{ODK_SERVER}/v1/projects/{PROJECT_ID}/forms/{FORM_ID}/submissions.csv"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Save CSV file
        filename = f"{OUTPUT_DIR}/{FORM_ID}_submissions.csv"
        with open(filename, "wb") as f:
            f.write(response.content)

        print(f"✅ Successfully downloaded: {filename}")

    except requests.RequestException as e:
        print(f"❌ Failed to download CSV: {e}")

def run_periodically():
    """Run the CSV download at regular intervals."""
    schedule.every(10).minutes.do(download_csv)  # Adjust interval as needed

    print("⏳ Scheduled CSV downloads every 10 minutes...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Wait before checking again

if __name__ == "__main__":
    download_csv()  # Run immediately
    run_periodically()  # Schedule future downloads
