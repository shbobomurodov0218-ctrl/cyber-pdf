from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from pypdf import PdfWriter, PdfMerger, PdfReader

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('temp', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'Fayl tanlanmadi!'}), 400

    pdf_path = None

    # Faqat PDF yuklash
    if all(f.filename.lower().endswith('.pdf') for f in files):
        merger = PdfMerger()
        for f in files:
            filename = secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
            merger.append(filepath)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'merged.pdf')
        with open(pdf_path, 'wb') as out:
            merger.write(out)
        merger.close()
    else:
        return jsonify({'error': 'Faqat PDF fayllar!'}), 400

    # PDF sahifalarini ro'yxat sifatida qaytarish
    reader = PdfReader(pdf_path)
    page_paths = []
    for i in range(len(reader.pages)):
        page_paths.append(f"/page/{i}")
    
    return jsonify({'pages': page_paths})

@app.route('/apply', methods=['POST'])
def apply_changes():
    data = request.json
    order = data.get('order', [])
    
    writer = PdfWriter()
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'merged.pdf')
    reader = PdfReader(pdf_path)
    
    for page_idx_str in order:
        try:
            idx = int(page_idx_str.split('_')[1])
            writer.add_page(reader.pages[idx])
        except:
            continue

    output_path = "temp/output.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)

    return jsonify({'download_url': '/download/output.pdf'})

@app.route('/page/<int:page_num>')
def page_preview(page_num):
    return "PDF sahifasi rasmi emas", 200

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(f"temp/{filename}", as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)