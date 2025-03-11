import os
import base64
import pytesseract
import requests
from pdf2image import convert_from_path
from flask import Flask, request, jsonify
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

app = Flask(__name__)
UPLOAD_FOLDER = "uploads/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Convert Image to Base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# OCR Processing
def process_ocr(image_path):
    return pytesseract.image_to_string(Image.open(image_path)).strip()

# Call Quen 2.5VL API
def call_quen_2_5vl(base64_image):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {
        "model": "Quen-2.5VL",
        "image": base64_image,
        "prompt": "Extract invoice details in JSON format"
    }
    response = requests.post("https://openrouter.ai/api/parse", headers=headers, json=payload)
    return response.json()

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files["file"]
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # Convert PDF to image if needed
    if file.filename.lower().endswith(".pdf"):
        images = convert_from_path(file_path)
        image_path = file_path.replace(".pdf", ".png")
        images[0].save(image_path, "PNG")
    else:
        image_path = file_path

    # Process OCR & Quen API
    base64_img = encode_image(image_path)
    ocr_text = process_ocr(image_path)
    quen_response = call_quen_2_5vl(base64_img)

    return jsonify({"OCR_Text": ocr_text, "Quen_Response": quen_response})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
