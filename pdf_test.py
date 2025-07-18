from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
import os, uuid

app = Flask(__name__)
app.secret_key = 'super_secret_key'
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

    # 假設你有實作 split_pdf 函數（之後可補上）
    #output_files = split_pdf(os.path.join(UPLOAD_FOLDER, filename), page_ranges)

    #flash(f"成功分割檔案，共產生 {len(output_files)} 份。", category="split")
    return redirect(url_for('split_pdf_page'))


if __name__ == '__main__':
    app.run(debug=True)
