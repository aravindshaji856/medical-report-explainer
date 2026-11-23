import base64
import io
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq
from PIL import Image

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")

SYSTEM_PROMPT = """You are a medical report explainer for patients. You read a photo of a lab report or a prescription and explain it in simple language.

STRICT RULES:
- NEVER diagnose any disease or condition.
- NEVER recommend, change, start or stop any treatment, medicine or dose.
- NEVER say what the results "mean" for the patient's health. Only describe what each test measures in general terms.
- Use short, simple words a non-medical person understands.
- Copy values exactly as printed. If something is unreadable, use null. Never guess.
- If the image is not a lab report or prescription, set report_type to "unknown".

Return ONLY valid JSON in this format:
{
  "report_type": "lab_report" | "prescription" | "unknown",
  "tests": [
    {"name": "", "value": "", "unit": "", "report_min": null, "report_max": null, "what_it_measures": ""}
  ],
  "medicines": [
    {"name": "", "dosage": "", "frequency": "", "duration": "", "what_it_is_for_simple": ""}
  ],
  "summary": "2-4 sentence plain-language overview of what this document contains",
  "questions_for_doctor": ["", "", ""]
}

Notes:
- For lab reports, fill "tests" and leave "medicines" empty. For prescriptions, do the opposite.
- report_min / report_max are the reference range printed on the report, as numbers. Use null if not printed.
- Do NOT decide whether a value is high or low. Our code does that.
- Give 5-8 useful questions the patient can ask their doctor."""


def prepare_image(image: Image.Image, max_side: int = 1600) -> str:
    """Shrink the image and return it as a base64 data URL."""
    image = image.convert("RGB")
    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def extract_json(text: str) -> dict:
    """Pull the JSON object out of the model's reply, even if it has extra text."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in model response")
    return json.loads(text[start:end + 1])


def analyze_report(image: Image.Image) -> dict:
    """Send the image to Groq and return the parsed JSON."""
    data_url = prepare_image(image)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Read this document and return the JSON."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=0.2,
        max_tokens=2500,
    )
    return extract_json(response.choices[0].message.content)


if __name__ == "__main__":
    # Quick test: put a sample report photo in the folder and set its name here
    img = Image.open("sample_report.jpg")
    print(json.dumps(analyze_report(img), indent=2))