
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

def list_task_lists():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds:
        return "Error: No token found."

    try:
        service = build('tasks', 'v1', credentials=creds)

        # Call the Tasks API
        results = service.tasklists().list(maxResults=10).execute()
        items = results.get('items', [])

        if not items:
            return "No task lists found."
        
        output = "Task Lists:\n"
        for item in items:
            output += f"{item['title']} ({item['id']})\n"
            
            # Get tasks for this list
            tasks = service.tasks().list(tasklist=item['id'], maxResults=5, showCompleted=False).execute()
            t_items = tasks.get('items', [])
            if t_items:
                for t in t_items:
                    output += f"  - [ ] {t['title']}\n"
            else:
                output += "  - (No active tasks)\n"

        return output

    except HttpError as error:
        return f"An error occurred: {error}"

if __name__ == '__main__':
    print(list_task_lists())
