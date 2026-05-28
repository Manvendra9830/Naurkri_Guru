'''
Naukri_Guru — AI-Powered Job Automation Platform
Developer: Manvendra Singh | IIIT Raichur

CSV to Excel export module with platform tracking.
License: GNU Affero General Public License (AGPL-3.0)
'''

import os
import pandas as pd
from config.settings import file_name, failed_file_name
from modules.helpers import print_lg, APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA, LEGACY_COLUMN_ALIASES, ensure_csv_header, safe_write_csv


def normalize_csv_file(csv_path: str, schema: list[str]):
    '''
    Reads a potentially jagged CSV and rewrites it to match the schema exactly.
    This fixes the 'Expected X fields, saw Y' error by standardizing all rows.
    '''
    if not os.path.exists(csv_path):
        return None

    # Step 1: Ensure robust header and row alignment using basic csv module
    ensure_csv_header(csv_path, schema)

    try:
        # Step 2: Load into pandas for higher-level cleaning
        df = pd.read_csv(csv_path, engine='python', on_bad_lines='warn', dtype=str, keep_default_na=False)
        
        # Standardize column names (legacy support)
        df = df.rename(columns={col: LEGACY_COLUMN_ALIASES.get(col, col) for col in df.columns})
        
        # Handle duplicates from renames
        if df.columns.duplicated().any():
            df = df.replace('', pd.NA).T.groupby(level=0).first().T.fillna('')

        # Ensure all columns exist
        for col in schema:
            if col not in df.columns:
                df[col] = ''

        # Data Cleaning / Standardizing
        if 'current_status' in df.columns:
            df['current_status'] = df['current_status'].fillna('')
            df.loc[df['current_status'].astype(str).str.strip() == '', 'current_status'] = 'Applied'

        if 'last_status_update' in df.columns:
            df['last_status_update'] = df['last_status_update'].fillna('')
            fallback_date = df.get('application_date', '')
            df.loc[df['last_status_update'].astype(str).str.strip() == '', 'last_status_update'] = fallback_date

        if 'status_source' in df.columns:
            df['status_source'] = df['status_source'].fillna('')
            df.loc[df['status_source'].astype(str).str.strip() == '', 'status_source'] = 'LinkedIn Automation'

        if 'response_received' in df.columns:
            df['response_received'] = df['response_received'].fillna('')
            df.loc[df['response_received'].astype(str).str.strip() == '', 'response_received'] = 'False'

        if 'source_platform' in df.columns:
            df['source_platform'] = df['source_platform'].fillna('')
            source_platform_blank = df['source_platform'].astype(str).str.strip().isin(['', 'Unknown'])
            df.loc[source_platform_blank, 'source_platform'] = 'LinkedIn'

        if 'runtime_segment' in df.columns:
            df['runtime_segment'] = df['runtime_segment'].fillna('')
            df.loc[df['runtime_segment'].astype(str).str.strip() == '', 'runtime_segment'] = 'production'

        segment_order = {
            'production': 0,
            'quarantined_recruiter': 1,
            'validation': 2,
            'dummy': 3,
            'review': 4,
        }
        if 'runtime_segment' in df.columns:
            df['_segment_order'] = df['runtime_segment'].map(segment_order).fillna(9)
            sort_columns = ['_segment_order']
            ascending = [True]
            if 'application_date' in df.columns:
                sort_columns.append('application_date')
                ascending.append(False)
            df = df.sort_values(sort_columns, ascending=ascending, kind='stable')
            df = df.drop(columns=['_segment_order'])

        # Filter to exact schema
        df = df[schema]
        
        # Save back to CSV to fix the physical file (ATOMIC)
        rows = df.to_dict('records')
        safe_write_csv(csv_path, schema, rows)
            
        return df
    except Exception as e:
        print_lg(f"⚠️ Warning: Normalization failed for {csv_path}: {e}")
        return None


def convert_csvs_to_excel():
    '''
    Converts application CSV files to Excel (.xlsx) format.
    First normalizes the CSVs to the centralized schema.
    '''
    try:
        # Normalize Applied Jobs
        if os.path.exists(file_name):
            try:
                df_applied = normalize_csv_file(file_name, APPLIED_EXPORT_SCHEMA)
                if df_applied is not None:
                    excel_applied = file_name.replace('.csv', '.xlsx')
                    with pd.ExcelWriter(excel_applied, engine='openpyxl') as writer:
                        df_applied.to_excel(writer, sheet_name='runtime_history', index=False)
                        if 'runtime_segment' in df_applied.columns:
                            segment_counts = df_applied['runtime_segment'].value_counts().rename_axis('runtime_segment').reset_index(name='rows')
                            segment_counts.to_excel(writer, sheet_name='summary', index=False)
                    print_lg(f"[EXPORT-SUCCESS] Applied jobs XLSX exported: rows={len(df_applied)}, xlsx={excel_applied}")
            except PermissionError:
                print_lg(f"❌ Cannot write to applied Excel — file is open in another program.")
            except Exception as e:
                print_lg(f"❌ Error exporting applied jobs: {e}")

        # Normalize Failed Jobs
        if os.path.exists(failed_file_name):
            try:
                df_failed = normalize_csv_file(failed_file_name, FAILED_EXPORT_SCHEMA)
                if df_failed is not None:
                    excel_failed = failed_file_name.replace('.csv', '.xlsx')
                    df_failed.to_excel(excel_failed, index=False)
                    print_lg(f"[EXPORT-SUCCESS] Failed jobs XLSX exported: rows={len(df_failed)}, xlsx={excel_failed}")
            except PermissionError:
                print_lg(f"❌ Cannot write to failed Excel — file is open in another program.")
            except Exception as e:
                print_lg(f"❌ Error exporting failed jobs: {e}")
                
    except Exception as e:
        print_lg(f"❌ Error in CSV to Excel conversion: {e}")


if __name__ == "__main__":
    convert_csvs_to_excel()
