from flask import Flask, request, render_template, send_file
from PIL import Image, ImageOps
from io import BytesIO
from dotenv import load_dotenv
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import os

load_dotenv()

app = Flask(__name__)

REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


@app.route("/")
def index():
    return render_template("index.html")


def process_single_image(input_image_bytes, skip_bg_removal=False, skip_cloudinary=False):
    """Remove background, enhance, and return a ready-to-paste passport PIL image.

    Args:
        input_image_bytes: BytesIO object with the image
        skip_bg_removal: If True, skip background removal and use original image
        skip_cloudinary: If True, skip Cloudinary upload/enhancement
    """
    img = None

    # Step 1: Background removal (optional)
    if not skip_bg_removal and REMOVE_BG_API_KEY:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": input_image_bytes},
            data={"size": "auto"},
            headers={"X-Api-Key": REMOVE_BG_API_KEY},
            timeout=30
        )

        if response.status_code == 200:
            # Background removal successful
            bg_removed = BytesIO(response.content)
            img = Image.open(bg_removed)

            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                processed_img = background
            else:
                processed_img = img.convert("RGB")
        else:
            # Background removal failed, return error info
            error_msg = f"bg_removal_failed:unknown:{response.status_code}"
            try:
                error_info = response.json()
                if error_info.get("errors"):
                    error_code = error_info["errors"][0].get("code", "unknown_error")
                    error_title = error_info["errors"][0].get("title", "")
                    error_msg = f"bg_removal_failed:{error_code}:{response.status_code}:{error_title}"
            except Exception:
                pass
            raise ValueError(error_msg)
    else:
        # Skip background removal, use original image
        # input_image_bytes could be bytes or BytesIO, handle both
        if isinstance(input_image_bytes, bytes):
            img = Image.open(BytesIO(input_image_bytes))
        else:
            input_image_bytes.seek(0)
            img = Image.open(input_image_bytes)
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            processed_img = background
        else:
            processed_img = img.convert("RGB")

    # Step 2: Upload to Cloudinary (optional - for AI enhancement)
    if not skip_cloudinary:
        try:
            buffer = BytesIO()
            processed_img.save(buffer, format="PNG")
            buffer.seek(0)
            upload_result = cloudinary.uploader.upload(buffer, resource_type="image", timeout=30)
            image_url = upload_result.get("secure_url")
            public_id = upload_result.get("public_id")

            if image_url and public_id:
                # Step 3: Enhance via Cloudinary AI
                enhanced_url = cloudinary.utils.cloudinary_url(
                    public_id,
                    transformation=[
                        {"effect": "gen_restore"},
                        {"quality": "auto"},
                        {"fetch_format": "auto"},
                    ],
                )[0]

                enhanced_img_data = requests.get(enhanced_url, timeout=30).content
                img = Image.open(BytesIO(enhanced_img_data))

                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    processed_img = background
                else:
                    processed_img = img.convert("RGB")
        except Exception as e:
            # Cloudinary failed, continue with original processed image
            print(f"Cloudinary enhancement skipped: {str(e)[:100]}")
            pass

    return processed_img


@app.route("/process", methods=["POST"])
def process():
    print("==== /process endpoint hit ====")

    # Layout settings
    passport_width = int(request.form.get("width", 390))
    passport_height = int(request.form.get("height", 480))
    border = int(request.form.get("border", 2))
    spacing = int(request.form.get("spacing", 10))
    margin_x = 10
    margin_y = 10
    horizontal_gap = 10
    a4_w, a4_h = 2480, 3508

    # Collect images and their copy counts
    # Supports: image_0, image_1, ... and copies_0, copies_1, ...
    # Also supports legacy single: image + copies
    images_data = []

    # Multi-image mode
    i = 0
    while f"image_{i}" in request.files:
        file = request.files[f"image_{i}"]
        copies = int(request.form.get(f"copies_{i}", 6))
        images_data.append((file.read(), copies))
        i += 1

    # Fallback to single image mode
    if not images_data and "image" in request.files:
        file = request.files["image"]
        copies = int(request.form.get("copies", 6))
        images_data.append((file.read(), copies))

    if not images_data:
        return "No image uploaded", 400

    # Check if user wants to skip background removal
    skip_bg_removal = request.form.get("skip_bg_removal", "false").lower() == "true"
    # Also skip Cloudinary when skipping BG removal (for faster processing)
    skip_cloudinary = skip_bg_removal

    print(f"DEBUG: Processing {len(images_data)} image(s), skip_bg_removal={skip_bg_removal}")

    # Process all images
    passport_images = []
    for idx, (img_bytes, copies) in enumerate(images_data):
        print(f"DEBUG: Processing image {idx + 1} with {copies} copies")
        try:
            img = process_single_image(img_bytes, skip_bg_removal=skip_bg_removal, skip_cloudinary=skip_cloudinary)
            img = img.resize((passport_width, passport_height), Image.LANCZOS)
            img = ImageOps.expand(img, border=border, fill="black")
            passport_images.append((img, copies))
        except ValueError as e:
            err_str = str(e)
            print(f"ERROR: {err_str}")
            if "410" in err_str or "face" in err_str.lower():
                return {"error": "face_detection_failed", "message": "Cannot detect face. Continue without BG removal?"}, 410
            elif "429" in err_str or "quota" in err_str.lower():
                return {"error": "quota_exceeded", "message": "API quota exceeded. Continue without BG removal?"}, 429
            elif "403" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower():
                return {"error": "api_key_invalid", "message": "API key invalid. Continue without BG removal?"}, 500
            else:
                return {"error": "bg_removal_failed", "message": "Background removal failed. Continue without BG removal?"}, 500
                

    paste_w = passport_width + 2 * border
    paste_h = passport_height + 2 * border

    # Build all pages
    pages = []
    current_page = Image.new("RGB", (a4_w, a4_h), "white")
    x, y = margin_x, margin_y

    def new_page():
        nonlocal current_page, x, y
        pages.append(current_page)
        current_page = Image.new("RGB", (a4_w, a4_h), "white")
        x, y = margin_x, margin_y

    for passport_img, copies in passport_images:
        for _ in range(copies):
            # Move to next row if needed
            if x + paste_w > a4_w - margin_x:
                x = margin_x
                y += paste_h + spacing

            # Move to next page if needed
            if y + paste_h > a4_h - margin_y:
                new_page()

            current_page.paste(passport_img, (x, y))
            print(f"DEBUG: Placed at x={x}, y={y}")
            x += paste_w + horizontal_gap

    pages.append(current_page)
    print(f"DEBUG: Total pages = {len(pages)}")

    # Export multi-page PDF
    output = BytesIO()
    if len(pages) == 1:
        pages[0].save(output, format="PDF", dpi=(300, 300))
    else:
        pages[0].save(
            output,
            format="PDF",
            dpi=(300, 300),
            save_all=True,
            append_images=pages[1:],
        )
    output.seek(0)
    print("DEBUG: Returning PDF to client")

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="passport-sheet.pdf",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)