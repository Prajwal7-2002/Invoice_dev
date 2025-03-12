import os
import base64
import pytesseract
import requests
import logging
from pdf2image import convert_from_path
from flask import Flask, request, jsonify
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Ensure the API key is provided
if not OPENROUTER_API_KEY:
    raise ValueError("Missing OpenRouter API Key. Set it in a .env file or environment variables.")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set Tesseract OCR path manually
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Poppler path for PDF conversion
POPPLER_PATH = r"C:\poppler-24.08.0\Library\bin"

app = Flask(__name__)
UPLOAD_FOLDER = "uploads/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Convert Image to Base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# OCR Processing
def process_ocr(image_path):
    try:
        return pytesseract.image_to_string(Image.open(image_path)).strip()
    except Exception as e:
        logging.error(f"OCR Processing failed: {e}")
        return ""

# Call Qwen 2.5VL API
def call_qwen_api(base64_image):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {
        "model": "qwen/qwen2.5-vl-72b-instruct",
        "messages": [
            {"role": "system", "content": "You are an AI that extracts invoice details in JSON format."},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract invoice details from this image and provide a structured JSON output."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        logging.info(f"Qwen API Response Status: {response.status_code}")
        return response.json() if response.status_code == 200 else {"error": "Qwen API call failed"}
    except requests.RequestException as e:
        logging.error(f"Failed to call Qwen API: {e}")
        return {"error": "Failed to reach OpenRouter API"}

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # Convert PDF to images
    image_paths = []
    if file.filename.lower().endswith(".pdf"):
        try:
            images = convert_from_path(file_path, poppler_path=POPPLER_PATH)
            for i, img in enumerate(images):
                image_path = file_path.replace(".pdf", f"_{i}.png")
                img.save(image_path, "PNG")
                image_paths.append(image_path)
        except Exception as e:
            logging.error(f"PDF to Image conversion failed: {e}")
            return jsonify({"error": "Failed to convert PDF to images"}), 500
    else:
        image_paths.append(file_path)

    # Process each image for OCR and Qwen API
    results = []
    for img_path in image_paths:
        base64_img = encode_image(img_path)
        ocr_text = process_ocr(img_path)
        qwen_response = call_qwen_api(base64_img)

        # Print the results in the terminal
        print("\n========== OCR Output ==========")
        print(ocr_text)
        print("\n========== Qwen API Response ==========")
        print(qwen_response)



        results.append({"image": img_path, "OCR_Text": ocr_text, "Qwen_Response": qwen_response})

    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
