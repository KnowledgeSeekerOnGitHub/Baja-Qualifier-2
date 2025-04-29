from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List
import pytesseract
from PIL import Image
import pandas as pd
import io

pytesseract.pytesseract.tesseract_cmd = r'tesseract.exe'

app = FastAPI()


def extract_lab_test_data(image: Image.Image):
    # OCR to dataframe
    data = pd.DataFrame(
        pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    )

    # Rebuild lines
    lines = {}
    for line_num in set(data["line_num"]):
        words = [data["text"][i] for i in range(len(data["text"])) if data["line_num"][i] == line_num]
        line_text = " ".join([w for w in words if w.strip() != ""])
        lines[line_num] = line_text

    formatted = [{"line_num": k, "text": v} for k, v in lines.items() if v.strip()]

    # Extract test lines
    results = []
    for i, item in enumerate(formatted):
        if "test" in item["text"].lower() or "result" in item["text"].lower():
            if i + 1 < len(formatted):
                line = formatted[i + 1]["text"].replace("__", "").strip()
                words = line.split()

                test_value = None
                test_unit = None
                bio_reference_range = None

                for j, word in enumerate(words):
                    if test_value is None and word.replace(".", "", 1).isdigit():
                        test_value = word
                        if j + 2 < len(words):
                            test_unit = words[j + 1]
                            bio_reference_range = words[j + 2]
                            break

                colon_index = line.find(":")
                test_name = line[:colon_index].strip() if colon_index != -1 else "Unknown"

                try:
                    value = float(test_value)
                    max_val = float(bio_reference_range.replace("mg/L", "").split("-")[-1].strip("<").strip())
                    lab_test_out_of_range = "High" if value > max_val else "Normal"
                except:
                    lab_test_out_of_range = "Unknown"

                results.append({
                    "test_name": test_name,
                    "test_value": test_value,
                    "bio_reference_range": bio_reference_range,
                    "test_unit": test_unit,
                    "lab_test_out_of_range": lab_test_out_of_range
                })

    return {
        "is_success": bool(results),
        "data": results if results else []
    }


@app.post("/get-lab-tests")
async def get_lab_tests(file: UploadFile = File(...)):
    try:
        image = Image.open(io.BytesIO(await file.read()))
        result = extract_lab_test_data(image)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"is_success": False, "error": str(e)})
