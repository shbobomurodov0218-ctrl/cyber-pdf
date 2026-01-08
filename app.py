from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from pdf2image import convert_from_path
from PyPDF2 import PdfWriter, PdfMerger, PdfReader
from PIL import Image
import io

# Poppler yo'lini qo'shish (agar mavjud bo'lsa)
poppler_path = r'C:\poppler\Library\bin'
if os.path.exists(poppler_path):
    os.environ["PATH"] += os.pathsep + poppler_path

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('temp', exist_ok=True)

# A4 formati (300 DPI)
A4_WIDTH_PX = 2480   # 210 mm
A4_HEIGHT_PX = 3508  # 297 mm

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'Fayl tanlanmadi!'}), 400

    pdf_path = None

    # 1. Agar faqat 1 ta PDF yuklangan bo'lsa
    if len(files) == 1 and files[0].filename.lower().endswith('.pdf'):
        f = files[0]
        filename = secure_filename(f.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(pdf_path)

    # 2. Agar bir nechta PDF yuklangan bo'lsa
    elif all(f.filename.lower().endswith('.pdf') for f in files):
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

    # 3. Agar bir nechta rasm yuklangan bo'lsa
    elif all(f.filename.lower().endswith(('.jpg', '.jpeg', '.png')) for f in files):
        images = []
        for f in files:
            img = Image.open(f.stream)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Faqat enini A4 eniga moslashtirish
            original_width, original_height = img.size
            new_width = A4_WIDTH_PX
            scale_factor = new_width / original_width
            new_height = int(original_height * scale_factor)
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)

            a4_page = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
            y_offset = (A4_HEIGHT_PX - new_height) // 2
            a4_page.paste(img_resized, (0, y_offset))
            images.append(a4_page)

        pdf_bytes = io.BytesIO()
        images[0].save(pdf_bytes, format='PDF', save_all=True, append_images=images[1:])
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'from_images.pdf')
        with open(pdf_path, 'wb') as out:
            out.write(pdf_bytes.getvalue())

    # 4. Aralash yuklash (PDF + rasm) — xato
    else:
        return jsonify({'error': 'Faqat PDF yoki JPG/PNG rasmlar!'}), 400

    # PDF sahifalarini rasmga aylantirish (tahrirlash uchun)
    try:
        images = convert_from_path(pdf_path, dpi=100)
    except Exception as e:
        return jsonify({'error': f'PDFni qayta ishlashda xatolik: {str(e)}'}), 500

    page_paths = []
    for i, img in enumerate(images):
        path = f"temp/page_{i}.jpg"
        img.save(path, 'JPEG')
        page_paths.append(f"/temp/page_{i}.jpg")
    
    return jsonify({'pages': page_paths})

@app.route('/apply', methods=['POST'])
def apply_changes():
    data = request.json
    page_order = data.get('order', [])
    crops = data.get('crops', {})

    writer = PdfWriter()

    for page_name in page_order:
        img_path = f"temp/{page_name}"
        if not os.path.exists(img_path):
            continue

        img = Image.open(img_path)
        if page_name in crops:
            crop_data = crops[page_name]
            x = crop_data.get('x', 0)
            y = crop_data.get('y', 0)
            w = crop_data.get('width', img.width)
            h = crop_data.get('height', img.height)
            img = img.crop((x, y, x + w, y + h))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Tahrirlangan rasmdan ham enini A4 eniga moslashtirish
        original_width, original_height = img.size
        new_width = A4_WIDTH_PX
        scale_factor = new_width / original_width
        new_height = int(original_height * scale_factor)
        img_resized = img.resize((new_width, new_height), Image.LANCZOS)

        a4_page = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
        y_offset = (A4_HEIGHT_PX - new_height) // 2
        a4_page.paste(img_resized, (0, y_offset))

        pdf_bytes = io.BytesIO()
        a4_page.save(pdf_bytes, format='PDF')
        pdf_bytes.seek(0)
        reader = PdfReader(pdf_bytes)
        writer.add_page(reader.pages[0])

    output_path = "temp/output.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)

    return jsonify({'download_url': '/download/output.pdf'})

@app.route('/temp/<filename>')
def temp_file(filename):
    response = send_file(f"temp/{filename}")
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(f"temp/{filename}", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)