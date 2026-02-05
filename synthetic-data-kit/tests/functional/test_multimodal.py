import os
import shutil
import subprocess
import pytest
import requests
import lance

# URL of a sample PDF with images for testing
PDF_URL = "https://www.adobe.com/support/products/enterprise/knowledgecenter/media/c4611_sample_explain.pdf"
PDF_FILENAME = "sample_multimodal.pdf"
OUTPUT_DIR = "test_output"

@pytest.fixture(scope="module")
def setup_module():
    """Download the test PDF and create the output directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    response = requests.get(PDF_URL)
    pdf_path = os.path.join(OUTPUT_DIR, PDF_FILENAME)
    with open(pdf_path, "wb") as f:
        f.write(response.content)

    yield

    # Teardown: remove the created directory and its contents
    shutil.rmtree(OUTPUT_DIR)

def run_cli_command(command):
    """Helper function to run a CLI command and return the output."""
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result

def test_ingest_pdf_default(setup_module):
    """Test default PDF ingestion (text only)."""
    pdf_path = os.path.join(OUTPUT_DIR, PDF_FILENAME)
    output_lance_path = os.path.join(OUTPUT_DIR, "sample_multimodal.lance")

    # Run the ingest command
    run_cli_command([
        "synthetic-data-kit", "ingest", pdf_path, "--output-dir", OUTPUT_DIR
    ])

    # Verify the output
    assert os.path.exists(output_lance_path)

    # Check the contents of the Lance dataset
    dataset = lance.dataset(output_lance_path)
    assert dataset.count_rows() > 0

    # Verify schema and data
    schema = dataset.schema
    assert "text" in schema.names
    assert "image" not in schema.names

    table = dataset.to_table()
    text_column = table.column("text")
    assert all(text is not None and len(text.as_py()) > 0 for text in text_column)

def test_ingest_pdf_multimodal(setup_module):
    """Test multimodal PDF ingestion (text and images)."""
    pdf_path = os.path.join(OUTPUT_DIR, PDF_FILENAME)
    output_lance_path = os.path.join(OUTPUT_DIR, "sample_multimodal.lance")

    # Clean up previous run if necessary
    if os.path.exists(output_lance_path):
        shutil.rmtree(output_lance_path)

    # Run the ingest command with the --multimodal flag
    run_cli_command([
        "synthetic-data-kit", "ingest", pdf_path, "--output-dir", OUTPUT_DIR, "--multimodal"
    ])

    # Verify the output
    assert os.path.exists(output_lance_path)

    # Check the contents of the Lance dataset
    dataset = lance.dataset(output_lance_path)
    assert dataset.count_rows() > 0

    # Verify schema and data
    schema = dataset.schema
    assert "text" in schema.names
    assert "image" in schema.names

    table = dataset.to_table()
    text_column = table.column("text")
    image_column = table.column("image")

    # Check that text and image data is not null where expected
    assert all(text is not None for text in text_column)

    # At least one image should be present in a multimodal PDF
    assert any(image is not None for image in image_column)
