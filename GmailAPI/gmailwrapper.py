"""
Minimal Gmail API wrapper for the WarnMe project.

This is inspired by the Java `Mailbox` class you showed, but:
- Only does READ-ONLY operations (no upload / label syncing).
- Focuses on just what you need:
    * connect to Gmail
    * search emails by sender / subject / time
    * load a full message (subject, sender, received time, body)
    * export results to CSV for later analysis

You already have:
  - credentials.json (OAuth client config from Google Cloud)
  - token.json       (created automatically after first login)
"""

import os
import base64
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Iterable, Dict, Any

from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# This scope is READ-ONLY access to Gmail.
# It matches what quickstart.py used.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# ---------------------------
# Data structure for 1 email
# ---------------------------
@dataclass
class EmailRecord:
    """
    Simple container for one email.

    This plays the same role as "Message + some extracted fields"
    in the Java Mailbox class, but flattened and easier to export.
    """
    id: str
    threadId: Optional[str]
    subject: Optional[str]
    sender: Optional[str]
    to: Optional[str]
    received_iso: Optional[str]      # Received date/time in ISO-8601 (UTC)
    snippet: Optional[str]
    body_text: Optional[str]         # Prefer text/plain, fallback to HTML
    labels: Optional[List[str]]      # label IDs (not names)


# -----------------------------
# Gmail API wrapper class
# -----------------------------
class GmailAPIWrapper:
    """
    Python version of a tiny 'Mailbox' wrapper:

    - Handles authentication (like Java's GmailService + connect())
    - Gives you high-level methods:
        * find_by_sender
        * find_by_subject
        * find_after_time
        * load_message
        * export_csv

    You will use THIS class from your WarnMe script,
    instead of talking directly to the Gmail API everywhere.
    """

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
        scopes: Optional[List[str]] = None,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes or SCOPES

        # This is like gmailService.getServiceWithRetries() in Java:
        # we end up with an authenticated Gmail client.
        self.service = self._build_service()

    # --------------------------
    # Auth / service setup
    # --------------------------
    def _build_service(self):
        """
        Equivalent to the auth + build() part of quickstart.py.

        - Uses token.json if it exists and is valid
        - Otherwise runs the OAuth flow in your browser
        - Returns a Gmail API 'service' object
        """
        creds: Optional[Credentials] = None

        # Try to load existing credentials from token.json
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)

        # If no valid creds, refresh or run login flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh existing token
                creds.refresh(Request())
            else:
                # First-time OAuth flow (opens browser)
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes
                )
                creds = flow.run_local_server(port=0)

            # Save refreshed/new credentials for next time
            with open(self.token_path, "w") as token_file:
                token_file.write(creds.to_json())

        # Build the Gmail API client (like new Gmail.Builder(...) in Java)
        return build("gmail", "v1", credentials=creds)

    # --------------------------
    # Helper: header lookup
    # --------------------------
    @staticmethod
    def _get_header(payload: Dict[str, Any], name: str) -> Optional[str]:
        """
        Given the 'payload' from a Gmail message and a header name
        (e.g., 'Subject', 'From', 'Date'), return its value.
        """
        for h in payload.get("headers", []):
            if h.get("name", "").lower() == name.lower():
                return h.get("value")
        return None

    # --------------------------
    # Helper: decode body
    # --------------------------
    def _decode_body(self, payload: Dict[str, Any]) -> str:
        """
        Extract the email body as text.

        Gmail messages can have:
          - a simple body (payload['body']['data'])
          - or nested 'parts' (multipart/alternative, text/plain, text/html)

        This is like the "_decode body" logic we saw in the Java Mailbox,
        but adapted to Python and base64 decoding.
        """
        def decode_b64(data: str) -> str:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
                "utf-8", errors="ignore"
            )

        # Case 1: direct body (no parts)
        body = payload.get("body", {})
        if "data" in body:
            return decode_b64(body["data"])

        # Case 2: multipart → search through parts
        parts = payload.get("parts", []) or []
        html_fallback = ""

        stack = list(parts)
        while stack:
            part = stack.pop()
            mime = part.get("mimeType", "")
            pbody = part.get("body", {})

            if "data" in pbody:
                text = decode_b64(pbody["data"])
                if mime == "text/plain":
                    # Prefer plain text
                    return text
                if mime == "text/html" and not html_fallback:
                    # Save HTML as a fallback if no plain text found
                    html_fallback = text

            # If this part has sub-parts, push them onto the stack
            subparts = part.get("parts", [])
            stack.extend(subparts or [])

        return html_fallback  # may be "" if nothing found

    # --------------------------
    # Helper: parse Date header
    # --------------------------
    @staticmethod
    def _parse_received_iso(date_header: Optional[str]) -> Optional[str]:
        """
        Convert the 'Date' header string into a normalized ISO-8601 UTC string.

        This mirrors what 'parse date' logic would do in Java, but we use
        Python's email.utils.parsedate_to_datetime.
        """
        if not date_header:
            return None
        try:
            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                # If timezone is missing, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
            # Normalize to UTC and return as ISO string
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

    # --------------------------
    # Helper: generic search
    # --------------------------
    def _search_message_ids(self, query: str, max_results: int = 100) -> List[str]:
        """
        Core search helper. Equivalent to:

            gmail.users().messages().list(userId, q=query, ...)

        Returns a list of message IDs matching the Gmail search query.
        This is analogous to Java's mapMessageIds using list().setQ("...").
        """
        user_id = "me"
        msgs: List[str] = []

        response = (
            self.service.users()
            .messages()
            .list(userId=user_id, q=query, maxResults=max_results)
            .execute()
        )

        for m in response.get("messages", []):
            msgs.append(m["id"])

        # NOTE: This is a simple version that doesn't chase nextPageToken.
        # For WarnMe, you probably don't have thousands and thousands,
        # but you can extend this later if needed.
        return msgs

    # --------------------------
    # Public: load one message
    # --------------------------
    def load_message(self, msg_id: str) -> EmailRecord:
        """
        Load a full Gmail message and convert it into an EmailRecord.

        Equivalent conceptually to Java's:
          gmail.users().messages().get(...).execute()
        plus some parsing of headers and body.
        """
        user_id = "me"

        msg = (
            self.service.users()
            .messages()
            .get(userId=user_id, id=msg_id, format="full")
            .execute()
        )

        payload = msg.get("payload", {})
        subject = self._get_header(payload, "Subject")
        sender = self._get_header(payload, "From")
        to = self._get_header(payload, "To")
        date_hdr = self._get_header(payload, "Date")

        received_iso = self._parse_received_iso(date_hdr)
        body_text = self._decode_body(payload)
        labels = msg.get("labelIds", [])

        return EmailRecord(
            id=msg.get("id"),
            threadId=msg.get("threadId"),
            subject=subject,
            sender=sender,
            to=to,
            received_iso=received_iso,
            snippet=msg.get("snippet"),
            body_text=body_text,
            labels=labels,
        )

    # --------------------------
    # Public: find email received time only
    # --------------------------
    def find_email_received_time(self, msg_id: str) -> Optional[str]:
        """
        If you only care about the time, this is a lighter version of load_message().
        It fetches in 'metadata' format (smaller payload).
        """
        user_id = "me"
        msg = (
            self.service.users()
            .messages()
            .get(
                userId=user_id,
                id=msg_id,
                format="metadata",
                metadataHeaders=["Date"],
            )
            .execute()
        )

        payload = msg.get("payload", {})
        date_hdr = self._get_header(payload, "Date")
        return self._parse_received_iso(date_hdr)

    # --------------------------
    # Public: find by sender
    # --------------------------
    def find_by_sender(
        self,
        sender_email: str,
        newer_than: Optional[str] = None,
        max_results: int = 100,
    ) -> List[EmailRecord]:
        """
        Search for emails from a specific sender, like:
            from:ucberkeley@warnme.berkeley.edu newer_than:30d

        This is the Python version of what your lead suggested:
        'change the search query to only search for email from ucberkeley@warnme.berkeley.edu'.
        """
        query = f"from:{sender_email}"
        if newer_than:
            # Gmail supports newer_than:30d, newer_than:6m, etc.
            query += f" newer_than:{newer_than}"

        msg_ids = self._search_message_ids(query, max_results=max_results)
        return [self.load_message(mid) for mid in msg_ids]

    # --------------------------
    # Public: find by subject
    # --------------------------
    def find_by_subject(
        self,
        subject_phrase: str,
        newer_than: Optional[str] = None,
        max_results: int = 100,
    ) -> List[EmailRecord]:
        """
        Search for emails whose subject contains a phrase, e.g.:
            subject:(WarnMe)
        """
        query = f'subject:("{subject_phrase}")'
        if newer_than:
            query += f" newer_than:{newer_than}"

        msg_ids = self._search_message_ids(query, max_results=max_results)
        return [self.load_message(mid) for mid in msg_ids]

    # --------------------------
    # Public: find after a time
    # --------------------------
    def find_after_time(
        self,
        dt_utc: datetime,
        sender_email: Optional[str] = None,
        max_results: int = 100,
    ) -> List[EmailRecord]:
        """
        Search for emails received strictly after a given datetime.

        Gmail 'after:' takes a UNIX timestamp (seconds since 1970-01-01).
        This is like the Java method that would use search queries with time filters.
        """
        # Ensure the datetime is timezone-aware and UTC
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        epoch = int(dt_utc.timestamp())

        query = f"after:{epoch}"
        if sender_email:
            query += f" from:{sender_email}"

        msg_ids = self._search_message_ids(query, max_results=max_results)
        return [self.load_message(mid) for mid in msg_ids]

    # --------------------------
    # Public: generic find
    # --------------------------
    def find(self, query: str, max_results: int = 100) -> List[EmailRecord]:
        """
        Fully flexible search if you want to write your own queries.

        Examples:
            'from:ucberkeley@warnme.berkeley.edu newer_than:180d'
            'subject:(WarnMe) after:1730784000'
        """
        msg_ids = self._search_message_ids(query, max_results=max_results)
        return [self.load_message(mid) for mid in msg_ids]

    # --------------------------
    # Public: export to CSV
    # --------------------------
    def export_csv(self, records: Iterable[EmailRecord], path: str) -> None:
        """
        Export a list of EmailRecord objects into a CSV file.

        This is analogous to a "save results" step you might do after
        label sync / import in Java, but here we just dump the data.
        """
        import csv

        rows = [asdict(r) for r in records]

        # If no records, still write a header row so the schema is visible.
        if not rows:
            fieldnames = [f.name for f in EmailRecord.__dataclass_fields__.values()]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return

        fieldnames = rows[0].keys()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

