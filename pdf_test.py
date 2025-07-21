from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from pypdf import PdfReader, PdfWriter
import os, uuid

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
        flash(f"成功上傳 {original_name} 至區塊 {target.upper()}！", category=target)

    return redirect(url_for('split_pdf_page' if target == 'split' else 'merge_pdf_page'))

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


if __name__ == '__main__':
    app.run(debug=True)
