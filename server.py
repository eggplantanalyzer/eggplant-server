import os
import uuid
import base64
import threading
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from rembg import remove
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import Image as ReportLabImage
import tempfile

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.gettempdir()
RESULTS_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def image_to_base64(image, size=(80, 80)):
    buffered = BytesIO()
    image.thumbnail(size, Image.LANCZOS)
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def calculate_color_percentages(image, mask):
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    masked_hsv = hsv[mask > 0]

    if masked_hsv.size == 0:
        return {"Black": 0, "Dark Purple": 0, "Light Purple": 0, "Brown": 0}

    total_pixels = masked_hsv.shape[0]
    color_percentages = {}

    color_ranges = {
        "Black": ((0, 0, 0), (180, 255, 80)),
        "Dark Purple": ((110, 50, 20), (160, 255, 100)),
        "Light Purple": ((110, 40, 100), (170, 255, 255)),
        "Brown": ((5, 40, 20), (40, 255, 200)),
    }

    for color, (lower, upper) in color_ranges.items():
        lower = np.array(lower, dtype=np.uint8)
        upper = np.array(upper, dtype=np.uint8)

        color_mask = (
            (masked_hsv[:, 0] >= lower[0]) & (masked_hsv[:, 0] <= upper[0]) &
            (masked_hsv[:, 1] >= lower[1]) & (masked_hsv[:, 1] <= upper[1]) &
            (masked_hsv[:, 2] >= lower[2]) & (masked_hsv[:, 2] <= upper[2])
        )

        color_pixels = np.count_nonzero(color_mask)
        color_percentages[color] = round((color_pixels / total_pixels) * 100, 2)

    return color_percentages

def process_single_image(image_path, idx):
    img = Image.open(image_path).convert("RGB")
    removed_bg = remove(img)
    image_np = np.array(removed_bg)
    
    if image_np.ndim == 2:
        image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
    
    avg_color = np.mean(image_np, axis=(0, 1)).astype(int)
    color_percentages = calculate_color_percentages(image_np, cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY))
    
    return {
        "id": idx + 1,
        "filename": os.path.basename(image_path),
        "original_image": image_to_base64(img),
        "processed_image": image_to_base64(removed_bg),
        "avg_color": f"RGB({avg_color[0]}, {avg_color[1]}, {avg_color[2]})",
        "color_percentages": color_percentages
    }

@app.route('/api/upload', methods=['POST'])
def upload_images():
    if 'files' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
    
    files = request.files.getlist('files')
    if len(files) == 0:
        return jsonify({"error": "No files selected"}), 400

    try:
        saved_paths = []
        for file in files:
            if file.filename == '':
                continue
            
            filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_paths.append(file_path)

        results = []
        for idx, path in enumerate(saved_paths):
            try:
                result = process_single_image(path, idx)
                results.append(result)
            except Exception as e:
                print(f"Error processing image {path}: {str(e)}")
                return jsonify({"error": f"Error processing image {os.path.basename(path)}: {str(e)}"}), 500

        # Generate Excel
        excel_filename = f"results_{uuid.uuid4()}.xlsx"
        excel_path = os.path.join(app.config['RESULTS_FOLDER'], excel_filename)
        
        df = pd.DataFrame([{
            "Image #": r["id"],
            "Filename": r["filename"],
            "Avg Color": r["avg_color"],
            "Black %": r["color_percentages"]["Black"],
            "Dark Purple %": r["color_percentages"]["Dark Purple"],
            "Light Purple %": r["color_percentages"]["Light Purple"],
            "Brown %": r["color_percentages"]["Brown"]
        } for r in results])
        
        df.to_excel(excel_path, index=False)

        # Generate PDF
        pdf_filename = f"report_{uuid.uuid4()}.pdf"
        pdf_path = os.path.join(app.config['RESULTS_FOLDER'], pdf_filename)
        threading.Thread(target=generate_pdf, args=(saved_paths, results, pdf_path)).start()

        return jsonify({
            "results": results,
            "excel_url": f"/static/results/{excel_filename}",
            "pdf_url": f"/static/results/{pdf_filename}"
        })

    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_pdf(image_paths, results, output_path):
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    for idx, (image_path, result) in enumerate(zip(image_paths, results)):
        # Modern header with subtle gray background
        c.setFillColorRGB(0.97, 0.97, 0.97)
        c.rect(0, height - 80, width, 80, fill=True, stroke=False)
        
        # Title and subtitle
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, height - 35, "Image Analysis Report")
        c.setFont("Helvetica", 9)
        c.drawString(30, height - 55, f"Sample {idx + 1}: {result['filename']}")
        
        # Images section - smaller images in a row
        img_width = 140
        img_height = 140
        img_y_position = height - 240
        
        # Original image
        c.setFont("Helvetica-Bold", 10)
        c.drawString(30, height - 90, "Original Image")
        img = Image.open(image_path)
        img.thumbnail((img_width, img_height))
        img_path = f"temp_{idx}_orig.png"
        img.save(img_path)
        c.drawImage(img_path, 30, img_y_position, width=img_width, height=img_height)
        os.remove(img_path)
        
        # Processed image
        c.drawString(190, height - 90, "Processed Image")
        processed_img = Image.open(BytesIO(base64.b64decode(result['processed_image'])))
        processed_img_path = f"temp_{idx}_proc.png"
        processed_img.save(processed_img_path)
        c.drawImage(processed_img_path, 190, img_y_position, width=img_width, height=img_height)
        os.remove(processed_img_path)
        
        # Color analysis section
        analysis_x = 360
        c.setFont("Helvetica-Bold", 10)
        c.drawString(analysis_x, height - 90, "Color Analysis")
        
        # Draw color percentage bars
        y_start = height - 120
        bar_height = 12
        max_bar_width = 150
        
        for i, (color_name, percentage) in enumerate(result['color_percentages'].items()):
            y = y_start - (i * (bar_height + 6))
            
            # Color label
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(analysis_x, y, f"{color_name}")
            
            # Background bar
            c.setFillColorRGB(0.95, 0.95, 0.95)
            c.rect(analysis_x + 80, y - 9, max_bar_width, bar_height, fill=True, stroke=False)
            
            # Percentage bar
            if color_name == "Black":
                c.setFillColorRGB(0.2, 0.2, 0.2)
            elif color_name == "Dark Purple":
                c.setFillColorRGB(0.3, 0.1, 0.3)
            elif color_name == "Light Purple":
                c.setFillColorRGB(0.6, 0.4, 0.6)
            else:  # Brown
                c.setFillColorRGB(0.6, 0.4, 0.2)
            
            bar_width = (percentage / 100) * max_bar_width
            c.rect(analysis_x + 80, y - 9, bar_width, bar_height, fill=True, stroke=False)
            
            # Percentage text
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(analysis_x + max_bar_width + 90, y, f"{percentage}%")
        
        # Average color section
        y_color_start = y_start - 80
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawString(analysis_x, y_color_start, "Average Color")
        
        # Parse RGB values
        rgb_str = result['avg_color']
        rgb_values = [int(x) for x in rgb_str.replace('RGB(', '').replace(')', '').split(',')]
        
        # Draw color square
        c.setFillColorRGB(rgb_values[0]/255, rgb_values[1]/255, rgb_values[2]/255)
        c.rect(analysis_x + 80, y_color_start - 9, 15, 15, fill=True)
        
        # RGB values
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.setFont("Helvetica", 9)
        c.drawString(analysis_x + 105, y_color_start, rgb_str)
        
        # Footer with page number
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.drawString(width/2 - 12, 20, f"{idx + 1}")
        
        c.showPage()
    
    c.save()

@app.route('/static/results/<path:filename>')
def serve_result(filename):
    return send_from_directory(app.config['RESULTS_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)