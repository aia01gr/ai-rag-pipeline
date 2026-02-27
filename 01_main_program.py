"""
Complete Setup Script - Run this to set up your RAG pipeline
"""

import os
import sys
from pathlib import Path


def print_header(text):
    print("\n" + "="*70)
    print(text)
    print("="*70 + "\n")


def print_step(step_num, text):
    print(f"\n{'='*3} STEP {step_num}: {text} {'='*3}\n")


def check_dependencies():
    """Check if required packages are installed"""
    print_step(1, "Checking Dependencies")

    required_packages = {
        'pdfplumber': 'PDF processing',
        'pypdf': 'PDF fallback',
        'chromadb': 'Vector database',
        'sentence_transformers': 'Local embeddings',
        'tqdm': 'Progress bars'
    }

    missing = []
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"✓ {package} ({description})")
        except ImportError:
            print(f"✗ {package} ({description}) - MISSING")
            missing.append(package)

    if missing:
        print(f"\n⚠️  Install missing packages:")
        print(f"pip install {' '.join(missing)}")
        return False

    print("\n✓ All dependencies installed!")
    return True


def setup_directories():
    """Create necessary directories"""
    print_step(2, "Setting Up Directories")

    directories = [
        './pdfs',           # For input PDFs
        './output',         # For processed files
        './chroma_db'       # For vector database
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created {directory}")

    print("\n✓ Directories ready!")


def process_pdfs():
    """Process PDFs and create chunks"""
    print_step(3, "Processing PDFs")

    from chunks_with_sentencesplitter import PDFProcessor

    pdf_dir = input("Enter path to your PDF directory [./pdfs]: ").strip() or './pdfs'

    if not os.path.exists(pdf_dir):
        print(f"⚠️  Directory {pdf_dir} not found. Skipping PDF processing.")
        return False

    pdf_files = list(Path(pdf_dir).rglob('*.pdf'))
    if not pdf_files:
        print(f"⚠️  No PDF files found in {pdf_dir}. Skipping.")
        return False

    print(f"Found {len(pdf_files)} PDF files")

    processor = PDFProcessor(
        chunk_size=1000,
        chunk_overlap=200,
        min_chunk_size=100
    )

    print("\nProcessing PDFs...")
    processor.process_directory(
        input_dir=pdf_dir,
        output_file='./output/chunks.json',
        batch_size=100,
        resume=True
    )

    print("\n✓ PDF processing complete!")
    return True


def generate_embeddings():
    """Generate embeddings for chunks"""
    print_step(4, "Generating Embeddings")

    if not os.path.exists('./output/chunks.json'):
        print("⚠️  No chunks.json found. Run PDF processing first.")
        return False

    from embeddings_with_voyage import EmbeddingGenerator

    print("\n START **********  Voyage ******** ")
    generator = EmbeddingGenerator()

    print("\nGenerating embeddings with **** Voyage **** ")
    generator.process_chunks_file(
        chunks_file='./output/chunks.json',
        output_file='./output/embedded_chunks.json',
        resume=True
    )
    print("\n✓ Embedding generation complete!")
    return True


def setup_vector_db():
    """Load embeddings into vector database"""
    print_step(5, "Setting Up Vector Database")

    if not os.path.exists('./output/embedded_chunks.json'):
        print("⚠️  No embedded_chunks.json found. Generate embeddings first.")
        return False

    from vector_database import VectorDatabase

    db = VectorDatabase(
        db_path="./chroma_db",
        collection_name="pdf_documents"
    )

    print("\nLoading embeddings into database...")
    num_loaded = db.load_embeddings(
        embedded_chunks_file='./output/embedded_chunks.json',
        batch_size=1000,
        reset=True
    )

    stats = db.get_collection_stats()
    print(f"\n✓ Vector database ready!")
    print(f"  - Total chunks: {stats['total_chunks']}")
    print(f"  - Location: {stats['db_path']}")

    return True


def test_rag_pipeline():
    """Test the RAG pipeline"""
    print_step(6, "Testing RAG Pipeline")

    from rag_pipeline import RAGPipeline

    pipeline = RAGPipeline(
        vector_db_path="./chroma_db",
        embedding_provider="sentence-transformers",
        embedding_model="all-MiniLM-L6-v2",
    )

    # Test query
    test_question = "What is this document about?"

    print(f"\nTest question: {test_question}")
    print("Querying...")

    try:
        result = pipeline.query(
            question=test_question,
            n_results=5
        )

        print("\n" + "-"*70)
        print("ANSWER:")
        print("-"*70)
        print(result['answer'])

        print(f"\n✓ RAG pipeline working! Used {result['usage']['output_tokens']} tokens")
        return True

    except Exception as e:
        print(f"\n⚠️  Error testing pipeline: {e}")
        return False


def print_next_steps():
    """Print next steps and usage examples"""
    print_header("SETUP COMPLETE!")

    print("""
Your RAG pipeline is ready to use! Here's how to use it:

1. INTERACTIVE MODE (recommended for testing):
   python rag_pipeline.py

2. PROGRAMMATIC USE:
   from rag_pipeline import RAGPipeline

   pipeline = RAGPipeline()
   result = pipeline.query("Your question here")
   print(result['answer'])

3. BATCH PROCESSING:
   questions = ["Q1", "Q2", "Q3"]
   results = pipeline.batch_query(questions)

4. CONVERSATIONAL MODE:
   history = []
   result = pipeline.conversational_query(
       question="Follow-up question",
       conversation_history=history
   )

FILES CREATED:
  - ./output/chunks.json          - Document chunks
  - ./output/embedded_chunks.json - Chunks with embeddings
  - ./chroma_db/                  - Vector database

SCRIPTS AVAILABLE:
  - chunks_with_sentencesplitter.py  - Process PDFs
  - embeddings_with_voyage.py        - Generate embeddings
  - vector_database.py      - Manage vector DB
  - rag_pipeline.py         - Complete RAG pipeline

📖 See README_RAG.md for detailed documentation
    """)


def main():
    """Run complete setup"""
    print_header("RAG PIPELINE SETUP")
    print("This script will guide you through setting up your RAG pipeline")
    print("for querying 1,000+ PDFs with 500K+ pages")

    # Run setup steps
    if not check_dependencies():
        print("\n❌ Install dependencies first: pip install -r requirements.txt")
        return

    setup_directories()

    # Ask user what they want to do
    print("\n" + "="*70)
    print("What would you like to do?")
    print("="*70)
    print("1. Complete setup (process PDFs → embeddings → vector DB → test)")
    print("2. Only process PDFs")
    print("3. Only generate embeddings (requires chunks.json)")
    print("4. Only setup vector DB (requires embedded_chunks.json)")
    print("5. Only test pipeline (requires setup to be complete)")

    choice = input("\nSelect option [1]: ").strip() or '1'

    if choice == '1':
        process_pdfs()
        generate_embeddings()
        setup_vector_db()
        test_rag_pipeline()
        print_next_steps()
    elif choice == '2':
        process_pdfs()
    elif choice == '3':
        generate_embeddings()
    elif choice == '4':
        setup_vector_db()
    elif choice == '5':
        test_rag_pipeline()
    else:
        print("Invalid option")


if __name__ == '__main__':
    main()
