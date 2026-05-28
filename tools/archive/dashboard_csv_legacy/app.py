

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import csv
from datetime import datetime
import os
from modules.helpers import APPLIED_EXPORT_SCHEMA, normalize_row

app = Flask(__name__)
CORS(app)

PATH = 'all excels/'
@app.route('/')
def home():
    """Displays the home page of the application."""
    return render_template('index.html')

@app.route('/applied-jobs', methods=['GET'])
def get_applied_jobs():
    '''
    Retrieves a list of applied jobs from the applications history CSV file.
    
    Returns a JSON response containing a list of jobs, each with details such as 
    job_id, title, company, recruiter fields, job links, and lifecycle status.
    
    If the CSV file is not found, returns a 404 error with a relevant message.
    If any other exception occurs, returns a 500 error with the exception message.
    '''

    try:
        jobs = []
        with open(PATH + 'all_applied_applications_history.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                normalized = normalize_row(row, APPLIED_EXPORT_SCHEMA, default_val='')
                date_applied = normalized.get('application_date', '')
                jobs.append({
                    'Job_ID': normalized.get('job_id', ''),
                    'Title': normalized.get('title', ''),
                    'Company': normalized.get('company', ''),
                    'HR_Name': normalized.get('recruiter_name', ''),
                    'HR_Link': normalized.get('recruiter_profile_url', ''),
                    'Job_Link': normalized.get('job_url', ''),
                    'External_Job_link': normalized.get('external_job_url', ''),
                    'Date_Applied': date_applied,
                    'application_date': date_applied,
                    'current_status': normalized.get('current_status', 'Applied'),
                    'last_status_update': normalized.get('last_status_update', date_applied),
                    'status_source': normalized.get('status_source', 'LinkedIn Automation'),
                    'response_received': normalized.get('response_received', 'False'),
                    'recruiter_email': normalized.get('recruiter_email', '')
                })
        return jsonify(jobs)
    except FileNotFoundError:
        return jsonify({"error": "No applications history found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/applied-jobs/<job_id>', methods=['PUT'])
def update_applied_date(job_id):
    """
    Updates the application_date field of a job in the applications history CSV file.

    Args:
        job_id (str): The Job ID of the job to be updated.

    Returns:
        A JSON response with a message indicating success or failure of the update
        operation. If the job is not found, returns a 404 error with a relevant
        message. If any other exception occurs, returns a 500 error with the
        exception message.
    """
    try:
        data = []
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Read current CSV content
        with open(csvPath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            found = False
            for row in reader:
                normalized = normalize_row(row, APPLIED_EXPORT_SCHEMA, default_val='')
                if normalized.get('job_id') == job_id:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    normalized['application_date'] = now
                    normalized['last_status_update'] = now
                    normalized['status_source'] = 'Manual API Update'
                    found = True
                data.append(normalized)
        
        if not found:
            return jsonify({"error": f"Job ID {job_id} not found"}), 404

        with open(csvPath, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=APPLIED_EXPORT_SCHEMA)
            writer.writeheader()
            writer.writerows(data)
        
        return jsonify({"message": "Date Applied updated successfully"}), 200
    except Exception as e:
        print(f"Error updating applied date: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

