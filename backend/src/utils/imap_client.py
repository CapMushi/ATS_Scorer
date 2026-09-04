import imaplib
import email
from email.header import decode_header
import os
import tempfile
import re
from datetime import datetime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

def decode_mime_words(s: str) -> str:
    """Decode MIME encoded strings."""
    if not s:
        return ""
    decoded_words = []
    for word, encoding in decode_header(s):
        if isinstance(word, bytes):
            try:
                decoded_words.append(word.decode(encoding or "utf-8", errors="replace"))
            except LookupError:
                decoded_words.append(word.decode("utf-8", errors="replace"))
        else:
            decoded_words.append(word)
    return "".join(decoded_words)

class IMAPClient:
    def __init__(self, email_address: str, app_password: str, imap_server: str = "imap.gmail.com"):
        self.email_address = email_address
        self.app_password = app_password
        self.imap_server = imap_server
        self.mail = None
        self.temp_dir = tempfile.mkdtemp(prefix="ats_cvs_")
        
        # Valid CV extensions
        self.valid_extensions = {'.pdf', '.docx', '.doc'}

    def connect(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.app_password)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            raise

    def fetch_cvs(self, since_date: str, subject_filter: str = "") -> List[Tuple[str, str, str]]:
        """
        Fetch CVs from emails.
        Returns a list of tuples: (file_path, original_filename, message_id)
        """
        if not self.mail:
            self.connect()

        self.mail.select("inbox")
        
        # Format date for IMAP (e.g. 20-Aug-2026)
        try:
            date_obj = datetime.strptime(since_date, "%Y-%m-%d")
            imap_date = date_obj.strftime("%d-%b-%Y")
        except ValueError:
            raise Exception("Invalid date format. Use YYYY-MM-DD")

        # Build search criteria
        search_criteria = f'(SINCE "{imap_date}")'
        if subject_filter:
            search_criteria += f' (SUBJECT "{subject_filter}")'
            
        status, messages = self.mail.search(None, search_criteria)
        if status != "OK":
            raise Exception(f"IMAP search failed: {status}")

        mail_ids = messages[0].split()
        downloaded_cvs = []

        for mail_id in mail_ids:
            status, msg_data = self.mail.fetch(mail_id, "(RFC822)")
            if status != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    message_id = msg.get("Message-ID", "")
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_maintype() == "multipart":
                                continue
                            if part.get("Content-Disposition") is None:
                                continue

                            filename = part.get_filename()
                            if filename:
                                filename = decode_mime_words(filename)
                                ext = os.path.splitext(filename)[1].lower()
                                
                                # STRICT FILTERING: Prevent downloading company_logo.png
                                if ext in self.valid_extensions:
                                    # Create safe filename
                                    safe_filename = re.sub(r'[^\w\-_\. ]', '_', filename)
                                    # Append message ID hash to prevent overwriting same names
                                    unique_id = str(hash(message_id))[-6:]
                                    filepath = os.path.join(self.temp_dir, f"{unique_id}_{safe_filename}")
                                    
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                        
                                    downloaded_cvs.append((filepath, filename, message_id))
        return downloaded_cvs

    def close(self):
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
