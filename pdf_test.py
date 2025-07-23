from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
import webbrowser
import zipfile
import requests
import threading
from tqdm import tqdm
import os, uuid

# -------- 自動下載 Poppler（Windows） -------- #
def get_poppler_path():
    poppler_root = os.path.join(os.getcwd(), 'poppler')
    if not os.path.exists(poppler_root):
        os.makedirs(poppler_root)

    # 嘗試尋找現有版本資料夾
    for folder in os.listdir(poppler_root):
        candidate = os.path.join(poppler_root, folder, 'Library', 'bin')
        if os.path.isdir(candidate):
            print(f"✅ 偵測到 Poppler 路徑：{candidate}")
            return candidate

    # 若無資料夾，自動下載最新版本
    print("⬇️ 未偵測到 Poppler，開始下載...")

    url = 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip'
    zip_path = os.path.join(os.getcwd(), 'poppler.zip')

    with requests.get(url, stream=True) as r:
        with open(zip_path, 'wb') as f:
            for chunk in tqdm(r.iter_content(chunk_size=8192)):
                f.write(chunk)

    print("🧩 解壓縮中...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(poppler_root)

    os.remove(zip_path)

    # 再次搜尋新解壓出來的版本資料夾
    for folder in os.listdir(poppler_root):
        candidate = os.path.join(poppler_root, folder, 'Library', 'bin')
        if os.path.isdir(candidate):
            print(f"✅ Poppler 安裝完成：{candidate}")
            return candidate

    raise Exception("❌ Poppler 安裝失敗，未找到 Library/bin")

# 全域 poppler_path 供 pdf2image 使用
POPLER_PATH = get_poppler_path()

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('home.html')  # 初始畫面

@app.route('/split')
def split_pdf_page():
    return render_template('split.html')

@app.route('/merge')
def merge_pdf_page():
    return render_template('merge.html')

@app.route('/reorder')
def reorder_pdf_page():
    return render_template('reorder.html')

@app.route('/upload/<target>', methods=['POST'])
def upload(target):
    uploaded_file = request.files['pdf_file']
    if uploaded_file.filename != '':
        original_name = uploaded_file.filename
        ext = os.path.splitext(original_name)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        uploaded_file.save(os.path.join(UPLOAD_FOLDER, filename))

        # Save to session separately by target
        session[f'{target}_original_name'] = original_name
        session[f'{target}_filename'] = filename
        if target == 'reorder':
            reader = PdfReader(os.path.join(UPLOAD_FOLDER, filename))
            session['reorder_total_pages'] = len(reader.pages)

            # 清空縮圖資料夾
            thumb_folder = os.path.join('static', 'thumbnails')
            os.makedirs(thumb_folder, exist_ok=True)
            for f in os.listdir(thumb_folder):
                os.remove(os.path.join(thumb_folder, f))

            # 轉換成圖檔
            images = convert_from_path(os.path.join(UPLOAD_FOLDER, filename), poppler_path = POPLER_PATH)
            for i, img in enumerate(images):
                img.save(os.path.join(thumb_folder, f'page_{i}.jpg'), 'JPEG')

        flash(f"成功上傳 {original_name} 至區塊 {target.upper()}！", category=target)

    if target.startswith('merge'):
        return redirect(url_for('merge_pdf_page'))
    elif target.startswith('split'):
        return redirect(url_for('split_pdf_page'))
    else:
        return redirect(url_for('reorder_pdf_page'))

@app.route('/uploads/<path:filename>')
def serve_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/perform_split', methods=['POST'])
def perform_split():
    page_ranges = request.form['page_ranges']
    filename = session.get('split_filename')

    if not filename:
        flash("沒有可供分割的檔案。請先上傳 PDF。", category="split")
        return redirect(url_for('split_pdf_page'))
    
    def parse_page_ranges(input_page_ranges_str):
        pages = set()
        parts = input_page_ranges_str.split(',')

        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                try:
                    start, end = int(start), int(end)
                    if start > end:
                        raise ValueError("起始頁不能大於結束頁")
                    pages.update(range(start, end + 1))
                except ValueError:
                    raise ValueError(f"無效的範圍格式：{part}")
            else:
                try:
                    pages.add(int(part))
                except ValueError:
                    raise ValueError(f"無效的頁碼：{part}")

        return sorted(pages)

    try:
        remove_pages = parse_page_ranges(page_ranges)
    except ValueError as e:
        flash(str(e), category="split")
        return redirect(url_for('split_pdf_page'))

    def split_pdf(file_path, remove_pages):
        reader = PdfReader(file_path)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        # 移除頁面是從1開始，但 PdfReader 是從0開始
        remove_indexes = set([p - 1 for p in remove_pages if 1 <= p <= total_pages])

        for i in range(total_pages):
            if i not in remove_indexes:
                writer.add_page(reader.pages[i])

        # 產生新檔名
        new_filename = f"split_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, new_filename)
        with open(output_path, 'wb') as f:
            writer.write(f)

        return new_filename

    # 執行分割
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    new_filename = split_pdf(input_path, remove_pages)

    flash(f"已刪除頁面 {remove_pages}，產生新檔案：{new_filename}", category="split")

    # 顯示下載連結
    session['split_result_file'] = new_filename
    return redirect(url_for('split_pdf_page'))

@app.route('/perform_merge', methods=['POST'])
def perform_merge():
    file1 = session.get("merge1_filename")
    file2 = session.get("merge2_filename")

    if not file1 or not file2:
        flash("請先上傳兩個 PDF 檔案才能進行合併。", category="merge")
        return redirect(url_for('merge_pdf_page'))
    
    file1_path = os.path.join(UPLOAD_FOLDER, file1)
    file2_path = os.path.join(UPLOAD_FOLDER, file2)

    def merge_pdf(file_path1, file_path2):
        reader1 = PdfReader(file_path1)
        reader2 = PdfReader(file_path2)
        writer = PdfWriter()
        # 加入第一份 PDF 的所有頁面
        for page in reader1.pages:
            writer.add_page(page)

        # 加入第二份 PDF 的所有頁面
        for page in reader2.pages:
            writer.add_page(page)

        # 儲存結果檔案
        new_merge_filename = f"merged_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, new_merge_filename)

        with open(output_path, 'wb') as f:
            writer.write(f)

        return new_merge_filename

    merged_filename = merge_pdf(file1_path, file2_path)

    session['merge_result_file'] = merged_filename
    flash(f"PDF 已成功合併，檔名為 {merged_filename}", category="merge")
    return redirect(url_for('merge_pdf_page'))

@app.route('/perform_reorder', methods= ['POST'])
def perform_reorder():
    filename = session.get("reorder_filename")
    
    if not filename:
        flash("沒有可供分割的檔案。請先上傳 PDF。", category="reorder")
        return redirect(url_for('split_pdf_page'))
    
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    return redirect(url_for('reorder_pdf_page'))


def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True)
