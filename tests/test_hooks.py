import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from malas.crews.write_format_crew.write_format_crew import WriteFormatCrew

# Setup directories
ARXIV_DIR = "arxiv_pdfs"

def setup_dummy_pdf():
    if not os.path.exists(ARXIV_DIR):
        os.makedirs(ARXIV_DIR)
    
    dummy_path = os.path.join(ARXIV_DIR, "hook_test.pdf")
    with open(dummy_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content")
    
    print(f"Created dummy PDF at {dummy_path}")
    return dummy_path

def test_hooks():
    print(">>> Testing WriteFormatCrew Hooks <<<")
    
    # 1. Setup
    pdf_path = setup_dummy_pdf()
    
    # 2. Initialize Crew (just the class wrapper)
    crew_wrapper = WriteFormatCrew()
    
    # 3. Test Ingestion Hook
    print("\n--- Testing @before_kickoff (ingest_pdfs) ---")
    inputs = {"topic": "test"}
    try:
        # We invoke the method. Note: In real execution, CrewAI calls this.
        # We just want to check the logic inside our defined method.
        # Check if the method is decorated correctly, it might be wrapped.
        # But we can still call it if it's bound.
        crew_wrapper.ingest_pdfs(inputs)
        print("ingest_pdfs executed successfully.")
    except Exception as e:
        print(f"FAILED ingest_pdfs: {e}")

    # 4. Test Cleanup Hook
    print("\n--- Testing @after_kickoff (cleanup_pdfs) ---")
    try:
        crew_wrapper.cleanup_pdfs("some output")
        print("cleanup_pdfs executed successfully.")
    except Exception as e:
        print(f"FAILED cleanup_pdfs: {e}")

    # 5. Verify Deletion
    if os.path.exists(pdf_path):
        print(f"❌ FAIL: PDF {pdf_path} still exists!")
    else:
        print(f"✅ PASS: PDF {pdf_path} was deleted.")

    # Cleanup directory if empty
    if os.path.exists(ARXIV_DIR) and not os.listdir(ARXIV_DIR):
        os.rmdir(ARXIV_DIR)

if __name__ == "__main__":
    test_hooks()
