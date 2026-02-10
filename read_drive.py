
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Use the same broad scopes as the main token
SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

# Project root (where token.json lives)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(PROJECT_ROOT, 'token.json')

def search_files(query="mimeType != 'application/vnd.google-apps.folder'", max_results=10):
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds:
        return "Error: No token found."

    try:
        service = build('drive', 'v3', credentials=creds)

        # Call the Drive API
        print(f"Searching for files: {query}")
        results = service.files().list(
            q=query, pageSize=max_results, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = results.get('files', [])

        if not items:
            return "No files found."
        
        output = "Files Found:\n"
        for item in items:
            output += f"{item['name']} ({item['mimeType']}) - ID: {item['id']}\n"

        return output

    except HttpError as error:
        return f"An error occurred: {error}"

if __name__ == '__main__':
    print(search_files())
