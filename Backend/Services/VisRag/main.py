from file_processing_pipeline import process_file_pipeline
from query_pipeline import query_pipeline
from pathlib import Path
import json

if __name__ == "__main__":
    pdf_path = "../Fact Sheet.pdf"
    file_id = ["fact_sheet_q3fy25"]

    # Step 1: Process the file (includes Pixtral relevance filtering)
    # process_file_pipeline(pdf_path, file_id)

    # # Step 2: Query the processed file
    query = "What is the operating margin in Q3FY25?"
    result = query_pipeline(file_id, query)
    # print(json.dumps(result, indent=2))