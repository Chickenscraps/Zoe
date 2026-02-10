
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
# If modifying these scopes, delete the file token.json.
# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform', # Access to Cloud APIs (Vision, Translation, etc.)
    'https://www.googleapis.com/auth/calendar',       # Full Calendar
    'https://www.googleapis.com/auth/gmail.modify',   # Read/Send Emails
    'https://www.googleapis.com/auth/drive',          # Full Drive
    'https://www.googleapis.com/auth/documents',      # Docs
    'https://www.googleapis.com/auth/spreadsheets',   # Sheets
    'https://www.googleapis.com/auth/tasks',          # Tasks
    'https://www.googleapis.com/auth/youtube.force-ssl' # YouTube
]

def authenticate_google_calendar():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found.")
                print("Please download it from Google Cloud Console and save it to this directory.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # Use local server (standard flow)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("Authentication successful! token.json saved.")
    
    return creds

if __name__ == '__main__':
    authenticate_google_calendar()
