
from pypdf import PdfReader
import sys

pdf_path = r"C:\Users\josha\OneDrive\Desktop\Clawd\research\Improving Clawdbot_ A Technical Strategy.pdf"

try:
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    print(text)
except Exception as e:
    print(f"Error: {e}")
