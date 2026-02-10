
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.readonly'
]

def get_recent_emails(max_results=5):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        # Assuming auth_calendar.py handles the refresh/login logic generally
        # giving a helpful error if token is missing/invalid for these scopes
        return "Error: Authentication required or token invalid. Run auth_calendar.py."

    try:
        service = build('gmail', 'v1', credentials=creds)

        # Call the Gmail API
        print(f"Getting last {max_results} emails...")
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return "No emails found."

        output = "Recent Emails:\n"
        for msg in messages:
            msg_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_detail.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = "No Subject"
            sender = "Unknown Sender"
            
            for h in headers:
                if h['name'] == 'Subject':
                    subject = h['value']
                if h['name'] == 'From':
                    sender = h['value']
            
            output += f"- From: {sender} | Subject: {subject}\n"

        return output

    except HttpError as error:
        return f"An error occurred: {error}"

if __name__ == '__main__':
    print(get_recent_emails())
