"""
PDF Document Processing and Chunking for RAG Pipeline
Handles 1,000+ PDFs with 500K+ pages efficiently
"""

import os
import csv
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from tqdm import tqdm
import pdfplumber
from pypdf import PdfReader
from llama_index.core.node_parser import SentenceSplitter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a single chunk of text with metadata"""
    chunk_id: str
    text: str
    source_file: str
    page_numbers: List[int]
    chunk_index: int
    total_chunks: int
    char_count: int
    metadata: Dict

    def to_dict(self):
        return asdict(self)


class PDFProcessor:
    """
    Processes PDFs and creates chunks suitable for RAG pipeline
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
        preserve_metadata: bool = True
    ):
        """
        Initialize PDF processor

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
            min_chunk_size: Minimum chunk size (discard smaller chunks)
            preserve_metadata: Whether to extract PDF metadata
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.preserve_metadata = preserve_metadata
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Extract text from PDF with page-level granularity

        Returns:
            List of dicts with page number and text
        """
        pages_data = []

        # Open file manually with bytes path to handle non-UTF-8 filenames on Linux
        path_bytes = os.fsencode(pdf_path)
        try:
            with open(path_bytes, 'rb') as f:
                with pdfplumber.open(f) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text:
                            pages_data.append({
                                'page_num': page_num,
                                'text': text.strip()
                            })

        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            # Fallback to pypdf if pdfplumber fails
            try:
                with open(path_bytes, 'rb') as fh:
                    reader = PdfReader(fh)
                    for page_num, page in enumerate(reader.pages, start=1):
                        text = page.extract_text()
                        if text:
                            pages_data.append({
                                'page_num': page_num,
                                'text': text.strip()
                            })
            except Exception as fallback_error:
                logger.error(f"Fallback also failed for {pdf_path}: {fallback_error}")

        return pages_data

    def extract_metadata(self, pdf_path: str) -> Dict:
        """Extract PDF metadata"""
        metadata = {
            'filename': os.path.basename(pdf_path),
            'filepath': pdf_path,
            'file_size': os.path.getsize(pdf_path)
        }

        if self.preserve_metadata:
            try:
                with open(os.fsencode(pdf_path), 'rb') as fh:
                    reader = PdfReader(fh)
                    pdf_meta = reader.metadata
                    if pdf_meta:
                        metadata.update({
                            'title': pdf_meta.title or '',
                            'author': pdf_meta.author or '',
                            'subject': pdf_meta.subject or '',
                            'creator': pdf_meta.creator or '',
                            'num_pages': len(reader.pages)
                        })
            except Exception as e:
                logger.warning(f"Could not extract metadata from {pdf_path}: {e}")

        return metadata

    def create_chunks(self, pages_data: List[Dict], metadata: Dict) -> List[DocumentChunk]:
        """
        Create sentence-aware chunks using LlamaIndex SentenceSplitter
        """
        # Build full text with page boundary markers for tracking
        page_boundaries = []  # (char_offset, page_num)
        full_text = ""
        for page_data in pages_data:
            page_boundaries.append((len(full_text), page_data['page_num']))
            full_text += page_data['text'] + "\n"

        # Use SentenceSplitter to split text
        split_texts = self.splitter.split_text(full_text)

        chunks = []
        search_start = 0
        for chunk_index, chunk_text in enumerate(split_texts):
            if len(chunk_text.strip()) < self.min_chunk_size:
                continue

            # Find which pages this chunk spans
            chunk_start = full_text.find(chunk_text, search_start)
            if chunk_start == -1:
                chunk_start = search_start
            chunk_end = chunk_start + len(chunk_text)
            search_start = chunk_start + 1

            page_nums = []
            for offset, page_num in page_boundaries:
                # Page covers from its offset to the next page's offset
                if offset <= chunk_end and page_num not in page_nums:
                    next_offsets = [o for o, _ in page_boundaries if o > offset]
                    page_end = next_offsets[0] if next_offsets else len(full_text)
                    if chunk_start < page_end:
                        page_nums.append(page_num)

            chunk_id = self._generate_chunk_id(metadata['filename'], chunk_index)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                source_file=metadata['filepath'],
                page_numbers=page_nums,
                chunk_index=chunk_index,
                total_chunks=-1,
                char_count=len(chunk_text),
                metadata=metadata
            )
            chunks.append(chunk)

        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _generate_chunk_id(self, filename: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        base = f"{filename}_{chunk_index}"
        return hashlib.md5(base.encode('utf-8', errors='replace')).hexdigest()[:16]

    def process_single_pdf(self, pdf_path: str) -> List[DocumentChunk]:
        """
        Process a single PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of DocumentChunk objects
        """
        logger.info(f"Processing {pdf_path}")

        # Extract text and metadata
        pages_data = self.extract_text_from_pdf(pdf_path)
        if not pages_data:
            logger.warning(f"No text extracted from {pdf_path}")
            return []

        metadata = self.extract_metadata(pdf_path)
        chunks = self.create_chunks(pages_data, metadata)

        logger.info(f"Created {len(chunks)} chunks from {pdf_path}")
        return chunks

    def process_directory(
        self,
        input_dir: str,
        output_file: str,
        batch_size: int = 100,
        resume: bool = True
    ) -> None:
        """
        Process all PDFs in a directory and subdirectories.

        Args:
            input_dir: Directory containing PDFs (recursive scan)
            output_file: JSON file to save chunks
            batch_size: Save progress every N files
            resume: Resume from last checkpoint if True
        """
        output_dir = os.path.dirname(os.path.abspath(output_file))
        os.makedirs(output_dir, exist_ok=True)

        todo_csv  = os.path.join(output_dir, 'todo.csv')
        skip_csv  = os.path.join(output_dir, 'skip.csv')
        done_csv  = os.path.join(output_dir, 'done.csv')
        error_csv = os.path.join(output_dir, 'error.csv')

        TODO_HEADERS  = ['date', 'full_path', 'filename']
        SKIP_HEADERS  = ['date', 'full_path', 'filename']
        DONE_HEADERS  = ['processed_date', 'full_path', 'filename', 'file_modified_date', 'file_size_bytes', 'processing_sec']
        ERROR_HEADERS = ['attempt_date', 'full_path', 'filename', 'file_modified_date', 'file_size_bytes', 'error_msg']

        # Load todo.csv full paths into a set once for efficient lookup
        todo_paths: set = set()
        if os.path.exists(todo_csv):
            with open(todo_csv, newline='', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) >= 2:
                        todo_paths.add(row[1].strip())

        # rglob handles subdirectories recursively
        pdf_files = list(Path(input_dir).rglob('*.pdf'))
        logger.info(f"Found {len(pdf_files)} PDF files (including subdirectories)")

        # Track progress
        processed_files = set()
        all_chunks = []

        # Resume from checkpoint if exists
        checkpoint_file = f"{output_file}.checkpoint"
        if resume and os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                processed_files = set(checkpoint['processed_files'])
                logger.info(f"Resuming: {len(processed_files)} files already processed")

        now_str = lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for idx, pdf_path in enumerate(tqdm(pdf_files, desc="Processing PDFs")):
            pdf_path_str = str(pdf_path.resolve())
            pdf_name     = pdf_path.name

            # Skip already processed in this session (checkpoint)
            if pdf_path_str in processed_files:
                continue

            # Check todo.csv — if already queued/processed, log to skip.csv and skip
            if pdf_path_str in todo_paths:
                self._csv_append(skip_csv, [now_str(), pdf_path_str, pdf_name], SKIP_HEADERS)
                logger.info(f"Skipped (already in todo): {pdf_path_str}")
                continue

            # Passed check — register in todo.csv before processing
            self._csv_append(todo_csv, [now_str(), pdf_path_str, pdf_name], TODO_HEADERS)
            todo_paths.add(pdf_path_str)

            # Collect file stats before processing
            try:
                stat = os.stat(pdf_path_str)
                file_size  = stat.st_size
                file_mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                file_size, file_mtime = 0, ''

            start_time = time.time()
            try:
                chunks = self.process_single_pdf(pdf_path_str)
                elapsed = round(time.time() - start_time, 2)

                if not chunks:
                    self._csv_append(
                        error_csv,
                        [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, "No text extracted (empty or unreadable PDF)"],
                        ERROR_HEADERS
                    )
                    logger.warning(f"No chunks extracted, logged to error: {pdf_path_str}")
                    continue

                all_chunks.extend(chunks)
                processed_files.add(pdf_path_str)

                # Log to done.csv
                self._csv_append(
                    done_csv,
                    [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, elapsed],
                    DONE_HEADERS
                )

                # Save checkpoint every batch_size files
                if (idx + 1) % batch_size == 0:
                    self._save_checkpoint(output_file, checkpoint_file, all_chunks, processed_files)

                # 5 sec pause after successful processing before next PDF
                time.sleep(5)

            except Exception as e:
                elapsed = round(time.time() - start_time, 2)
                error_msg = str(e)[:200]

                # Log to error.csv
                self._csv_append(
                    error_csv,
                    [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, error_msg],
                    ERROR_HEADERS
                )
                logger.error(f"Failed to process {pdf_path_str}: {e}")
                continue

        # Final save
        self._save_chunks(output_file, all_chunks)
        logger.info(f"Processing complete! Total chunks: {len(all_chunks)}")

        # Clean up checkpoint
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)

    def _save_checkpoint(
        self,
        output_file: str,
        checkpoint_file: str,
        chunks: List[DocumentChunk],
        processed_files: set
    ):
        """Save progress checkpoint"""
        # Save chunks
        self._save_chunks(output_file, chunks)

        # Save checkpoint
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'processed_files': list(processed_files),
                'total_chunks': len(chunks)
            }, f)

        logger.info(f"Checkpoint saved: {len(processed_files)} files, {len(chunks)} chunks")

    def _save_chunks(self, output_file: str, chunks: List[DocumentChunk]):
        """Save chunks to JSON file"""
        with open(output_file, 'w', encoding='utf-8', errors='replace') as f:
            json.dump(
                [chunk.to_dict() for chunk in chunks],
                f,
                indent=2,
                ensure_ascii=False
            )

    def _csv_append(self, filepath: str, row: list, headers: list) -> None:
        """Append one row to a semicolon-delimited CSV, creating it with headers if needed."""
        file_exists = os.path.exists(filepath)
        try:
            with open(filepath, 'a', newline='', encoding='utf-8', errors='replace') as f:
                writer = csv.writer(f, delimiter=';')
                if not file_exists:
                    writer.writerow(headers)
                writer.writerow(row)
        except Exception as e:
            logger.warning(f"Could not write to {filepath}: {e}")


def main():
    """Example usage"""
    # Initialize processor
    processor = PDFProcessor(
        chunk_size=1000,      # ~1000 characters per chunk
        chunk_overlap=200,    # 200 character overlap
        min_chunk_size=100    # Discard chunks < 100 chars
    )

    # Process single PDF
    # chunks = processor.process_single_pdf('example.pdf', chunking_strategy='fixed')
    # print(f"Created {len(chunks)} chunks")

    # Process entire directory
    processor.process_directory(
        input_dir='./pdfs',              # Your PDF directory
        output_file='./chunks.json',      # Output file
        batch_size=100,                   # Save every 100 files
        resume=True                       # Resume if interrupted
    )


if __name__ == '__main__':
    main()
