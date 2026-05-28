import os
import csv
from modules.helpers import APPLIED_EXPORT_SCHEMA, ensure_csv_header
from config.settings import file_name

def create_test_data():
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    
    # Ensure header is correct
    ensure_csv_header(file_name, APPLIED_EXPORT_SCHEMA)
    
    test_rows = [
        {
            'job_id': 'TEST-001',
            'title': 'SDE 1',
            'company': 'Acme Labs',
            'recruiter_email': 'cs22b1054@iiitr.ac.in',
            'recruiter_name': 'Test Recruiter',
            'job_description': 'Test JD for SDE 1 role.',
            'application_date': '2026-05-25 12:00:00',
            'current_status': 'Applied',
            'source_platform': 'LinkedIn',
            'recruiter_email_confidence': '1.0',
            'recruiter_email_source': 'manual_test'
        },
        {
            'job_id': 'TEST-002',
            'title': 'ML Engineer',
            'company': 'FutureAI',
            'recruiter_email': 'manvendras606@gmail.com',
            'recruiter_name': 'AI Hiring Manager',
            'job_description': 'Test JD for ML Engineer role.',
            'application_date': '2026-05-25 12:05:00',
            'current_status': 'Applied',
            'source_platform': 'LinkedIn',
            'recruiter_email_confidence': '0.9',
            'recruiter_email_source': 'manual_test'
        }
    ]
    
    # Check if they already exist to avoid duplicates
    existing_ids = set()
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row.get('job_id'))

    with open(file_name, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=APPLIED_EXPORT_SCHEMA)
        for row in test_rows:
            if row['job_id'] not in existing_ids:
                # Pad row with empty strings for missing fields
                full_row = {col: row.get(col, "") for col in APPLIED_EXPORT_SCHEMA}
                writer.writerow(full_row)
                print(f"Added test row: {row['job_id']}")
            else:
                print(f"Test row {row['job_id']} already exists.")

if __name__ == "__main__":
    # Add project root to sys.path if needed
    import sys
    sys.path.append(os.getcwd())
    create_test_data()
