import os
import shutil
import glob
from crewai_tools import ArxivPaperTool
from malas.tools.custom_tool import PaperRagTool

# Setup
ARXIV_DIR = "arxiv_pdfs"
if not os.path.exists(ARXIV_DIR):
    os.makedirs(ARXIV_DIR)

def run_integration_test():
    print(">>> 1. Downloading Paper from Arxiv...")
    # NOTE: ArxivPaperTool by default doesn't let us easily pick directory, 
    # it usually downloads to CWD. We'll search for PDFs in CWD after run.
    # We'll search for a specific topic, e.g., "DeepSeek".
    topic = "DeepSeek LLM" 
    # Check if we already have PDFs
    existing_pdfs = glob.glob(os.path.join(ARXIV_DIR, "*.pdf"))
    if existing_pdfs:
        print(f"Configs: {len(existing_pdfs)} PDFs already exist in {ARXIV_DIR}. Skipping download.")
        pdfs = existing_pdfs
    else:
        print(f"Searching for: {topic}")
        try:
            tool = ArxivPaperTool(download_pdfs=True)
            result = tool.run(topic)
            print("Arxiv Search Result Snippet:", result[:200], "...")
        except Exception as e:
            print(f"❌ Arxiv search failed: {e}")
            return

    # Move downloaded PDFs to arxiv_pdfs
    print("\n>>> 2. Moving PDFs to 'arxiv_pdfs'...")
    # Arxiv tool usually saves as <article_id>.pdf or similar in CWD
    # We'll just grab all .pdf files in root created recently? 
    # Or just all pdfs in root for this test.
    root_pdfs = glob.glob("*.pdf")
    for pdf in root_pdfs:
        dest = os.path.join(ARXIV_DIR, pdf)
        shutil.move(pdf, dest)
        print(f"Moved {pdf} -> {dest}")

    # Check if we have PDFs
    pdfs = glob.glob(os.path.join(ARXIV_DIR, "*.pdf"))
    if not pdfs:
        print("❌ No PDFs found in arxiv_pdfs. Download might have failed or ArxivTool behavior is different.")
        # Create a dummy if real download failed, just to test RAG? 
        # But user wants to test Arxiv flow. Let's proceed only if we have pdfs.
        return

    print(f"\n>>> 3. Ingesting {len(pdfs)} PDFs into PaperRagTool...")
    rag_tool = PaperRagTool(collection_name="integration_test_db")
    
    for pdf in pdfs:
        try:
            rag_tool.add_paper(os.path.abspath(pdf))
        except Exception as e:
            print(f"❌ Failed to ingest {pdf}: {e}")

    print("\n>>> 4. Testing RAG Query...")
    # Query something relevant to the topic
    query = "What are the capabilities of DeepSeek?"
    print(f"Query: {query}")
    
    try:
        answer = rag_tool.run(query)
        print("\n=== RAG RESULT ===")
        print(answer)
        print("==================")
    except Exception as e:
        print(f"❌ Query failed: {e}")

    # Cleanup
    print("\n>>> 5. Cleanup...")
    # Uncomment to keep files for inspection if needed
    # for pdf in pdfs:
    #     os.remove(pdf)
    # if os.path.exists(ARXIV_DIR) and not os.listdir(ARXIV_DIR):
    #     os.rmdir(ARXIV_DIR)
    print("Done. (Files left in 'arxiv_pdfs' for inspection)")

if __name__ == "__main__":
    run_integration_test()
