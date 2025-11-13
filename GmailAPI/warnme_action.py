# warnme_action.py
from datetime import datetime, timezone
from gmailwrapper import GmailAPIWrapper   # adjust path if needed

SENDER = "ucberkeley@warnme.berkeley.edu"
CSV_OUT = "warnme_emails.csv"

def main():
    mailbox = GmailAPIWrapper()

    # Example 1: find WarnMe emails by sender from the last 180 days
    records = mailbox.find_by_sender(SENDER, newer_than="180d", max_results=200)

    # Example 2 (alternative): find by subject text
    # records = mailbox.find_by_subject("WarnMe", newer_than="180d", max_results=200)

    # Example 3 (alternative): find everything after a specific date
    # dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    # records = mailbox.find_after_time(dt, sender_email=SENDER)

    print(f"Found {len(records)} WarnMe emails.")
    mailbox.export_csv(records, CSV_OUT)
    print(f"Exported to {CSV_OUT}")

if __name__ == "__main__":
    main()
