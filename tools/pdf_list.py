"""
Δημιουργεί το /ai/output/pdf_list.csv με όλα τα PDF αρχεία
από τον φάκελο /ai/pdfs και τους υποφακέλους του.

Στήλες: filename ; full_path ; size_bytes
"""

import csv
import os
from pathlib import Path

INPUT_DIR  = '/ai/PDF'
OUTPUT_CSV = '/ai/output/pdf_list.csv'

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

pdf_files = sorted(Path(INPUT_DIR).rglob('*.pdf'), key=lambda p: str(p))

with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8', errors='replace') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(['filename', 'full_path', 'size_bytes'])
    for p in pdf_files:
        try:
            size = p.stat().st_size
        except Exception:
            size = ''
        writer.writerow([p.name, str(p.resolve()), size])

print(f"Δημιουργήθηκε: {OUTPUT_CSV}")
print(f"Σύνολο PDF: {len(pdf_files)}")
