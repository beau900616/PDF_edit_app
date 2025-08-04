from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
import webbrowser
import zipfile
import requests
import threading
from tqdm import tqdm
import os, uuid

from pdf_utils import get_poppler_path
from pdf_utils import parse_page_ranges, InvalidPageRangeError
from pdf_utils import split_pdf, merge_pdf, reorder_pdf
import config

# 全域 poppler_path 供 pdf2image 使用
POPLER_PATH = get_poppler_path()

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

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
        uploaded_file.save(os.path.join(config.UPLOAD_FOLDER, filename))

        # Save to session separately by target
        session[f'{target}_original_name'] = original_name
        session[f'{target}_filename'] = filename

        if target == 'reorder':
            reader = PdfReader(os.path.join(config.UPLOAD_FOLDER, filename))
            session['reorder_total_pages'] = len(reader.pages)

            # 清空縮圖資料夾
            thumb_folder = os.path.join('static', 'thumbnails')
            os.makedirs(thumb_folder, exist_ok=True)
            for f in os.listdir(thumb_folder):
                os.remove(os.path.join(thumb_folder, f))

            # 轉換成圖檔
            images = convert_from_path(os.path.join(config.UPLOAD_FOLDER, filename), poppler_path = POPLER_PATH)
            for i, img in enumerate(images):
                img.save(os.path.join(thumb_folder, f'page_{i}.jpg'), 'JPEG')

        flash(f"成功上傳 {original_name} 至區塊 {target.upper()}！", category=target)

    if target.startswith('merge'):
        return redirect(url_for('merge_pdf_page'))
    elif target.startswith('split'):
        return redirect(url_for('split_pdf_page'))
    else:
        return redirect(url_for('reorder_pdf_page'))

@app.route('/downloads/<path:filename>')
def serve_pdf(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)

@app.route('/perform_split', methods=['POST'])
def perform_split():
    page_ranges = request.form['page_ranges']
    filename = session.get('split_filename')

    if not filename:
        flash("沒有可供分割的檔案。請先上傳 PDF。", category="split")
        return redirect(url_for('split_pdf_page'))
    
    try:
        remove_pages = parse_page_ranges(page_ranges)
    except InvalidPageRangeError as e:
        print(str(e))
        flash(str(e), category="split")
        return redirect(url_for('split_pdf_page'))

    # 執行分割
    input_path = os.path.join(config.UPLOAD_FOLDER, filename)
    new_filename = split_pdf(input_path, remove_pages, config.UPLOAD_FOLDER)

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
    
    file1_path = os.path.join(config.UPLOAD_FOLDER, file1)
    file2_path = os.path.join(config.UPLOAD_FOLDER, file2)
    merged_filename = merge_pdf(file1_path, file2_path, config.UPLOAD_FOLDER)

    session['merge_result_file'] = merged_filename
    flash(f"PDF 已成功合併，檔名為 {merged_filename}", category="merge")
    return redirect(url_for('merge_pdf_page'))

@app.route('/perform_reorder', methods= ['POST'])
def perform_reorder():
    filename = session.get("reorder_filename")
    new_order_str = request.form.get("save_new_order")
    
    if not filename or not new_order_str:
        flash("缺少檔案或頁面順序資料。請重新上傳。", category="reorder")
        return redirect(url_for('reorder_pdf_page'))
    
    # 分析頁面順序（前端傳來的字串，例如："0,1,2"）
    try:
        new_order = [int(i) for i in new_order_str.split(',')]
    except ValueError:
        flash("頁面順序資料格式錯誤。", category="reorder")
        return redirect(url_for('reorder_pdf_page'))
    
    input_path = os.path.join(config.UPLOAD_FOLDER, filename)    
    new_filename = reorder_pdf(input_path, new_order, config.UPLOAD_FOLDER)
    
    session['reorder_result_file'] = new_filename
    flash(f"✅ PDF 排序完成，新檔案：{new_filename}", category="reorder")
    return redirect(url_for('reorder_pdf_page'))

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True)
