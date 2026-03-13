import fitz  # PyMuPDF

doc = fitz.open(r"C:\ANUP\MTP\Proposing\Codes For COOJA\LAAKA\LAAKA.pdf")
with open(r"C:\ANUP\MTP\Proposing\Codes For COOJA\LAAKA\LAAKA_text.txt", "w", encoding="utf-8") as f:
    for i, page in enumerate(doc):
        f.write(f"\n{'='*80}\nPAGE {i+1}\n{'='*80}\n")
        f.write(page.get_text())
num_pages = len(doc)
doc.close()
print(f"Done. Extracted {num_pages} pages.")
