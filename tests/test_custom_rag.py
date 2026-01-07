import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from malas.tools.custom_tool import PaperRagTool

def create_dummy_pdf(filename="dummy_paper.pdf"):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(filename)
    c.drawString(100, 750, "This is a dummy scientific paper for testing.")
    c.drawString(100, 730, "It contains some random text to be chunked by Chonkie.")
    c.drawString(100, 710, "Sentence one. Sentence two. Sentence three.")
    c.save()
    return filename

def test_rag_tool():
    print(">>> 1. Initializing PaperRagTool...")
    try:
        tool = PaperRagTool(collection_name="test_collection")
        print("PaperRagTool initialized successfully.")
    except Exception as e:
        print(f"FAILED to initialize tool: {e}")
        return

    print("\n>>> 2. Creating Dummy PDF...")
    pdf_path = create_dummy_pdf()
    print(f"Created {pdf_path}")

    print("\n>>> 3. Adding PDF to Knowledge Base (should trigger Chonkie)...")
    try:
        # We need to make sure the path is absolute for safety
        abs_path = os.path.abspath(pdf_path)
        tool.add_paper(abs_path)
        print("Add paper triggered.")
    except Exception as e:
        print(f"FAILED to add paper: {e}")
    
    # Clean up
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        print("Dummy PDF removed.")

if __name__ == "__main__":
    test_rag_tool()
