from pypdf import PdfReader, PdfWriter
import uuid
import os
import zipfile
import requests
from tqdm import tqdm

import config

# -------- 自動下載 Poppler（Windows） -------- #
def get_poppler_path():
    poppler_root = os.path.join(os.getcwd(), config.POPLER_FOLDER_NAME)
    if not os.path.exists(poppler_root):
        os.makedirs(poppler_root)

    # 嘗試尋找現有版本資料夾
    for folder in os.listdir(poppler_root):
        candidate = os.path.join(poppler_root, folder, config.POPLER_EXTRACT_SUBPATH)
        if os.path.isdir(candidate):
            print(f"✅ 偵測到 Poppler 路徑：{candidate}")
            return candidate

    # 若無資料夾，自動下載最新版本
    print("⬇️ 未偵測到 Poppler，開始下載...")

    zip_path = os.path.join(os.getcwd(), 'poppler.zip')

    with requests.get(config.POPLER_DOWNLOAD_URL, stream=True) as r:
        with open(zip_path, 'wb') as f:
            for chunk in tqdm(r.iter_content(chunk_size=8192)):
                f.write(chunk)

    print("🧩 解壓縮中...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(poppler_root)

    os.remove(zip_path)

    # 再次搜尋新解壓出來的版本資料夾
    for folder in os.listdir(poppler_root):
        candidate = os.path.join(poppler_root, folder, config.POPLER_EXTRACT_SUBPATH)
        if os.path.isdir(candidate):
            print(f"✅ Poppler 安裝完成：{candidate}")
            return candidate

    raise Exception("❌ Poppler 安裝失敗，未找到 Library/bin")

class InvalidPageRangeError(Exception):
    pass

def parse_page_ranges(input_str):
    try:
        result = set()
        parts = input_str.split(",")
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start >= end:
                    raise InvalidPageRangeError(f"頁碼範圍錯誤：{start}-{end} 順序不正確")
                result.update(range(start, end + 1))
            else:
                result.add(int(part))
        return sorted(result)
    except Exception:
        raise InvalidPageRangeError("格式錯誤，請輸入像是 1,3-5 這樣的格式")

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

def reorder_pdf(file_path, new_order, upload_folder):
    reader = PdfReader(file_path)
    writer = PdfWriter()
    # 重建 PDF 按照排序順序
    for i in new_order:
        writer.add_page(reader.pages[i])    
    # 輸出檔案
    new_filename = f"reordered_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, new_filename)
    with open(output_path, 'wb') as f:
        writer.write(f)
    return new_filename