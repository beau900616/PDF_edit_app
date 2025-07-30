from pypdf import PdfReader, PdfWriter
import uuid
import os

def split_pdf(file_path, remove_pages, upload_folder):
    reader = PdfReader(file_path)
    writer = PdfWriter()
    total_pages = len(reader.pages)
    remove_indexes = set([p - 1 for p in remove_pages if 1 <= p <= total_pages])
    for i in range(total_pages):
        if i not in remove_indexes:
            writer.add_page(reader.pages[i])
    new_filename = f"split_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, new_filename)
    with open(output_path, 'wb') as f:
        writer.write(f)
    return new_filename

def merge_pdf(file_path1, file_path2, upload_folder):
    reader1 = PdfReader(file_path1)
    reader2 = PdfReader(file_path2)
    writer = PdfWriter()
    for page in reader1.pages:
        writer.add_page(page)
    for page in reader2.pages:
        writer.add_page(page)
    new_filename = f"merged_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, new_filename)
    with open(output_path, 'wb') as f:
        writer.write(f)
    return new_filename