"""
PDF Document Processing and Chunking for RAG Pipeline
Uses Docling for structure-aware extraction (tables, multi-column, OCR)
Drop-in replacement for chunks_with_sentencesplitter.py — same output format
"""

import os
import csv
import json
import time
import psutil
import hashlib
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, Future, BrokenExecutor

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.chunking import HybridChunker
from transformers import AutoTokenizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
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


# ---------------------------------------------------------------------------
# Worker process helpers — must be at module level for pickling
# ---------------------------------------------------------------------------
_worker_processor = None


def _worker_init(chunk_size: int, chunk_overlap: int, min_chunk_size: int,
                 ocr: bool, table_structure: bool) -> None:
    """Initialise PDFProcessor once per worker process."""
    global _worker_processor
    _worker_processor = PDFProcessor(chunk_size, chunk_overlap, min_chunk_size,
                                     ocr, table_structure)


def _process_pdf_task(pdf_path_str: str):
    """Process one PDF in a worker process; return (path, chunks)."""
    global _worker_processor
    return pdf_path_str, _worker_processor.process_single_pdf(pdf_path_str)
# ---------------------------------------------------------------------------


class PDFProcessor:

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
        ocr: bool = True,
        table_structure: bool = True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.ocr = ocr
        self.table_structure = table_structure

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = ocr
        pipeline_options.do_table_structure = table_structure

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        # Load tokenizer with extended max length to avoid truncation warnings.
        # HybridChunker uses it only for token counting, not inference.
        tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        tokenizer.model_max_length = 1_000_000

        self.chunker = HybridChunker(
            tokenizer=tokenizer,
            max_tokens=chunk_size,
            merge_peers=True,
        )

    def process_single_pdf(self, pdf_path: str) -> List[DocumentChunk]:
        logger.info(f"Processing {pdf_path}")

        try:
            result = self.converter.convert(pdf_path)
        except Exception as e:
            logger.error(f"Docling conversion failed for {pdf_path}: {e}")
            return []

        doc = result.document
        chunk_iter = self.chunker.chunk(doc)

        filename = os.path.basename(pdf_path)
        file_size = os.path.getsize(pdf_path)
        num_pages = len(doc.pages) if doc.pages else 0

        metadata = {
            "filename": filename,
            "filepath": pdf_path,
            "file_size": file_size,
            "num_pages": num_pages,
        }

        chunks: List[DocumentChunk] = []
        for chunk_index, chunk in enumerate(chunk_iter):
            text = chunk.text.strip()
            if len(text) < self.min_chunk_size:
                continue

            # Extract page numbers from provenance
            page_numbers = []
            for item in chunk.meta.doc_items:
                for prov in item.prov:
                    pn = prov.page_no
                    if pn not in page_numbers:
                        page_numbers.append(pn)
            page_numbers.sort()

            chunk_id = hashlib.md5(
                f"{filename}_{chunk_index}".encode("utf-8", errors="replace")
            ).hexdigest()[:16]

            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=text,
                source_file=pdf_path,
                page_numbers=page_numbers,
                chunk_index=chunk_index,
                total_chunks=-1,
                char_count=len(text),
                metadata=metadata,
            ))

        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        logger.info(f"Created {len(chunks)} chunks from {filename}")
        return chunks

    def process_directory(
        self,
        input_dir: str,
        output_file: str,
        batch_size: int = 100,
        resume: bool = True,
        num_workers: int = 4,
        cpu_limit: float = 80.0,
    ) -> None:
        output_dir = os.path.dirname(os.path.abspath(output_file))
        os.makedirs(output_dir, exist_ok=True)

        todo_csv  = os.path.join(output_dir, "todo.csv")
        skip_csv  = os.path.join(output_dir, "skip.csv")
        done_csv  = os.path.join(output_dir, "done.csv")
        error_csv = os.path.join(output_dir, "error.csv")

        TODO_HEADERS  = ["date", "full_path", "filename"]
        SKIP_HEADERS  = ["date", "full_path", "filename"]
        DONE_HEADERS  = ["processed_date", "full_path", "filename", "file_modified_date", "file_size_bytes", "processing_sec"]
        ERROR_HEADERS = ["attempt_date", "full_path", "filename", "file_modified_date", "file_size_bytes", "error_msg"]

        todo_paths: set = set()
        if os.path.exists(todo_csv):
            with open(todo_csv, newline="", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        todo_paths.add(row[1].strip())

        pdf_files = list(Path(input_dir).rglob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        processed_files: set = set()
        all_chunks: List[DocumentChunk] = []

        checkpoint_file = f"{output_file}.checkpoint"
        if resume and os.path.exists(checkpoint_file):
            with open(checkpoint_file, "r") as f:
                checkpoint = json.load(f)
                processed_files = set(checkpoint["processed_files"])
                logger.info(f"Resuming: {len(processed_files)} files already processed")

        # Φόρτωσε existing chunks από chunks.json ώστε να μην χαθούν σε crash/restart
        if resume and os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                all_chunks = [DocumentChunk(**c) for c in saved]
                logger.info(f"Loaded {len(all_chunks)} existing chunks from {output_file}")
            except Exception as e:
                logger.warning(f"Could not load existing chunks: {e}")
                all_chunks = []

        now_str = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Separate pending PDFs from already processed / to skip
        pending: List[Path] = []
        for pdf_path in pdf_files:
            pdf_path_str = str(pdf_path.resolve())
            pdf_name = pdf_path.name

            if pdf_path_str in processed_files:
                continue

            # todo.csv skip: μόνο σε fresh run (όχι resume) για να αποφύγουμε
            # re-processing. Σε resume βασιζόμαστε ΜΟΝΟ στο checkpoint.
            if not resume and pdf_path_str in todo_paths:
                self._csv_append(skip_csv, [now_str(), pdf_path_str, pdf_name], SKIP_HEADERS)
                logger.info(f"Skipped (already in todo): {pdf_name}")
                continue

            self._csv_append(todo_csv, [now_str(), pdf_path_str, pdf_name], TODO_HEADERS)
            todo_paths.add(pdf_path_str)
            pending.append(pdf_path)

        logger.info(f"PDFs to process: {len(pending)} | Workers: {num_workers} | CPU limit: {cpu_limit}%")

        if not pending:
            logger.info("Nothing to process.")
            self._save_chunks(output_file, all_chunks)
            return

        completed_count = 0
        # future -> (pdf_path_str, pdf_name, file_mtime, file_size, start_time)
        active: Dict[Future, tuple] = {}

        def _drain_completed(pbar) -> int:
            """Collect all done futures, update state, return count drained."""
            nonlocal completed_count
            done = [f for f in active if f.done()]
            for future in done:
                pdf_path_str, pdf_name, file_mtime, file_size, t0 = active.pop(future)
                elapsed = round(time.time() - t0, 2)
                try:
                    _, chunks = future.result()
                    if not chunks:
                        self._csv_append(
                            error_csv,
                            [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, "No text extracted"],
                            ERROR_HEADERS,
                        )
                        logger.warning(f"No chunks: {pdf_name}")
                    else:
                        all_chunks.extend(chunks)
                        processed_files.add(pdf_path_str)
                        self._csv_append(
                            done_csv,
                            [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, elapsed],
                            DONE_HEADERS,
                        )
                        completed_count += 1
                        logger.info(
                            f"[{completed_count}] Done: {pdf_name} "
                            f"({elapsed}s, {len(chunks)} chunks, active: {len(active)})"
                        )
                        if completed_count % batch_size == 0:
                            self._save_checkpoint(output_file, checkpoint_file, all_chunks, processed_files)
                except Exception as e:
                    self._csv_append(
                        error_csv,
                        [now_str(), pdf_path_str, pdf_name, file_mtime, file_size, str(e)[:200]],
                        ERROR_HEADERS,
                    )
                    logger.error(f"Failed: {pdf_name}: {e}")
                pbar.update(1)
            return len(done)

        def _wait_for_cpu() -> None:
            """Block until total CPU usage drops below cpu_limit."""
            cpu = psutil.cpu_percent(interval=1)
            while cpu > cpu_limit:
                logger.debug(f"CPU {cpu:.0f}% > {cpu_limit:.0f}%, waiting before next submit...")
                time.sleep(2)
                cpu = psutil.cpu_percent(interval=0.5)

        def _make_executor():
            return ProcessPoolExecutor(
                max_workers=num_workers,
                max_tasks_per_child=10,
                initializer=_worker_init,
                initargs=(self.chunk_size, self.chunk_overlap, self.min_chunk_size,
                          self.ocr, self.table_structure),
            )

        with tqdm(total=len(pending), desc="Processing PDFs") as pbar:
            pending_iter = iter(pending)
            exhausted = False
            executor = _make_executor()

            while not exhausted or active:
                # 1. Collect any completed futures
                _drain_completed(pbar)

                # 2. Submit new tasks while we have free slots
                while not exhausted and len(active) < num_workers:
                    _wait_for_cpu()

                    try:
                        pdf_path = next(pending_iter)
                    except StopIteration:
                        exhausted = True
                        break

                    pdf_path_str = str(pdf_path.resolve())
                    pdf_name = pdf_path.name
                    try:
                        stat = os.stat(pdf_path_str)
                        file_size = stat.st_size
                        file_mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        file_size, file_mtime = 0, ""

                    try:
                        future = executor.submit(_process_pdf_task, pdf_path_str)
                        active[future] = (pdf_path_str, pdf_name, file_mtime, file_size, time.time())
                        logger.info(f"Submitted: {pdf_name} (active: {len(active)})")
                    except BrokenExecutor:
                        # Worker κρασάρισε (OOM) — σώζουμε checkpoint και κάνουμε restart pool
                        logger.warning("BrokenProcessPool detected — saving checkpoint and restarting pool...")
                        self._save_checkpoint(output_file, checkpoint_file, all_chunks, processed_files)
                        # Τα active futures είναι χαμένα — καταγράφουμε ως error
                        for f, (p, n, mt, sz, t0) in list(active.items()):
                            self._csv_append(error_csv,
                                [now_str(), p, n, mt, sz, "Pool crash"],
                                ERROR_HEADERS)
                            pbar.update(1)
                        active.clear()
                        executor.shutdown(wait=False)
                        time.sleep(5)
                        executor = _make_executor()
                        logger.info("Pool restarted.")
                        # Επαναϋποβολή του τρέχοντος PDF
                        try:
                            future = executor.submit(_process_pdf_task, pdf_path_str)
                            active[future] = (pdf_path_str, pdf_name, file_mtime, file_size, time.time())
                            logger.info(f"Re-submitted: {pdf_name}")
                        except Exception as e2:
                            logger.error(f"Re-submit failed: {pdf_name}: {e2}")

                # 3. If nothing completed yet, yield briefly before next check
                if active:
                    time.sleep(0.5)

            executor.shutdown(wait=True)

        self._save_chunks(output_file, all_chunks)
        logger.info(f"Done. Total chunks: {len(all_chunks)}")

        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)

    def _save_checkpoint(self, output_file, checkpoint_file, chunks, processed_files):
        self._save_chunks(output_file, chunks)
        with open(checkpoint_file, "w") as f:
            json.dump({"processed_files": list(processed_files), "total_chunks": len(chunks)}, f)
        logger.info(f"Checkpoint: {len(processed_files)} files, {len(chunks)} chunks")

    def _save_chunks(self, output_file, chunks):
        with open(output_file, "w", encoding="utf-8", errors="replace") as f:
            json.dump([c.to_dict() for c in chunks], f, indent=2, ensure_ascii=False)

    def _csv_append(self, filepath, row, headers):
        file_exists = os.path.exists(filepath)
        try:
            with open(filepath, "a", newline="", encoding="utf-8", errors="replace") as f:
                writer = csv.writer(f, delimiter=";")
                if not file_exists:
                    writer.writerow(headers)
                writer.writerow(row)
        except Exception as e:
            logger.warning(f"Could not write to {filepath}: {e}")


def main():
    processor = PDFProcessor(
        chunk_size=1000,
        chunk_overlap=200,
        min_chunk_size=100,
        ocr=False,
        table_structure=True,
    )

    processor.process_directory(
        input_dir="./pdfs",
        output_file="./chunks.json",
        batch_size=20,
        resume=True,
        num_workers=4,    # ~3-4GB RAM ανά worker → 4 workers ≈ 12-16GB
        cpu_limit=80.0,   # περιμένει να πέσει κάτω από 80% πριν κάθε νέα υποβολή
    )


if __name__ == "__main__":
    main()
