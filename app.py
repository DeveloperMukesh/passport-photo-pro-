from flask import Flask, request, render_template, send_file, jsonify
from PIL import Image, ImageOps
from io import BytesIO
from dotenv import load_dotenv
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import os
import json
from datetime import datetime

app = Flask(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

def load_settings_from_file():
    """Load settings from settings.json file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings.json: {e}")
    return None

def save_settings_to_file(settings_data):
    """Save settings to settings.json file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings.json: {e}")
        return False

def apply_settings(settings_data):
    """Apply settings to environment variables and configure services"""
    # Set environment variables
    for key, value in settings_data.items():
        if key not in ['configured', 'last_updated'] and value:
            os.environ[key] = value
    
    # Reconfigure Cloudinary
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

# Try loading from .env file first (for development)
env_loaded = load_dotenv()

# If .env not loaded or incomplete, try settings.json (for production)
if not env_loaded or not os.getenv("REMOVE_BG_API_KEY"):
    settings = load_settings_from_file()
    if settings and settings.get('configured'):
        apply_settings(settings)
        print("Loaded configuration from settings.json")

# Global variables
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")

# Paper size definitions (width, height in pixels at 300 DPI)
PAPER_SIZES = {
    '4R': {'width': 1200, 'height': 1800, 'label': '4R (4"×6")', 'description': 'Standard photo print size'},
    'A4': {'width': 2480, 'height': 3508, 'label': 'A4', 'description': 'International standard paper size'},
    'Letter': {'width': 2550, 'height': 3300, 'label': 'Letter (8.5"×11")', 'description': 'US standard paper size'},
    '5R': {'width': 1500, 'height': 2100, 'label': '5R (5"×7")', 'description': 'Medium photo print size'},
    '6R': {'width': 1800, 'height': 2400, 'label': '6R (6"×8")', 'description': 'Large photo print size'},
    '3R': {'width': 1050, 'height': 1500, 'label': '3R (3.5"×5")', 'description': 'Small photo print size'},
}

def get_paper_size(paper_type='4R'):
    """Get paper dimensions for the specified paper type"""
    if paper_type in PAPER_SIZES:
        return PAPER_SIZES[paper_type]
    return PAPER_SIZES['4R']  # Default to 4R


@app.route("/")
def index():
    return render_template("index.html", paper_sizes=PAPER_SIZES)


@app.route("/get-paper-sizes", methods=["GET"])
def get_paper_sizes():
    """Return available paper sizes"""
    return jsonify({
        "paper_sizes": {k: v for k, v in PAPER_SIZES.items()},
        "default": "4R"
    })


@app.route("/settings")
def settings_page():
    """Settings page for managing environment variables"""
    settings = load_settings_from_file()
    if not settings:
        settings = {
            "CLOUDINARY_CLOUD_NAME": "",
            "CLOUDINARY_API_KEY": "",
            "CLOUDINARY_API_SECRET": "",
            "REMOVE_BG_API_KEY": "",
            "configured": False,
            "last_updated": None
        }
    
    return render_template("settings.html", 
                         settings=settings,
                         configured=settings.get('configured', False),
                         last_updated=settings.get('last_updated'))


@app.route("/upload-env", methods=["POST"])
def upload_env():
    """Upload and parse .env file"""
    if 'env_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['env_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.env'):
        return jsonify({"error": "Please upload a .env file"}), 400
    
    try:
        # Read and parse the .env file
        content = file.read().decode('utf-8')
        settings = {}
        
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                settings[key.strip()] = value.strip()
        
        # Validate required keys
        required_keys = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 
                        'CLOUDINARY_API_SECRET', 'REMOVE_BG_API_KEY']
        missing_keys = [k for k in required_keys if k not in settings]
        
        if missing_keys:
            return jsonify({
                "error": f"Missing required keys: {', '.join(missing_keys)}"
            }), 400
        
        # Add metadata
        settings['configured'] = True
        settings['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save to settings.json
        if save_settings_to_file(settings):
            # Apply the settings
            apply_settings(settings)
            global REMOVE_BG_API_KEY
            REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
            
            return jsonify({
                "message": "Settings saved successfully! Reloading..."
            })
        else:
            return jsonify({"error": "Failed to save settings"}), 500
            
    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


@app.route("/save-settings", methods=["POST"])
def save_settings():
    """Save settings from manual entry"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Validate required fields
    required_keys = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 
                    'CLOUDINARY_API_SECRET', 'REMOVE_BG_API_KEY']
    missing_keys = [k for k in required_keys if k not in data or not data[k].strip()]
    
    if missing_keys:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing_keys)}"
        }), 400
    
    # Create settings object
    settings = {
        'CLOUDINARY_CLOUD_NAME': data['CLOUDINARY_CLOUD_NAME'].strip(),
        'CLOUDINARY_API_KEY': data['CLOUDINARY_API_KEY'].strip(),
        'CLOUDINARY_API_SECRET': data['CLOUDINARY_API_SECRET'].strip(),
        'REMOVE_BG_API_KEY': data['REMOVE_BG_API_KEY'].strip(),
        'configured': True,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Save to settings.json
    if save_settings_to_file(settings):
        # Apply the settings
        apply_settings(settings)
        global REMOVE_BG_API_KEY
        REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
        
        return jsonify({
            "message": "Settings saved successfully! Reloading..."
        })
    else:
        return jsonify({"error": "Failed to save settings"}), 500


@app.route("/test-settings", methods=["POST"])
def test_settings():
    """Test the current configuration"""
    results = []
    
    # Test Cloudinary configuration
    try:
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = os.getenv("CLOUDINARY_API_KEY")
        api_secret = os.getenv("CLOUDINARY_API_SECRET")
        
        if cloud_name and api_key and api_secret:
            # Try a simple Cloudinary operation
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            results.append({
                "name": "Cloudinary Configuration",
                "status": "pass",
                "message": "Valid configuration"
            })
        else:
            results.append({
                "name": "Cloudinary Configuration",
                "status": "fail",
                "message": "Missing credentials"
            })
    except Exception as e:
        results.append({
            "name": "Cloudinary Configuration",
            "status": "fail",
            "message": str(e)
        })
    
    # Test Remove.bg API key
    try:
        remove_bg_key = os.getenv("REMOVE_BG_API_KEY")
        if remove_bg_key:
            # Make a test request to remove.bg API (using a minimal request)
            response = requests.get(
                "https://api.remove.bg/v1.0/account",
                headers={"X-Api-Key": remove_bg_key},
                timeout=10
            )
            
            if response.status_code == 200:
                account_data = response.json()
                credits = account_data.get('data', {}).get('attributes', {}).get('credits', {}).get('total', 'Unknown')
                results.append({
                    "name": "Remove.bg API",
                    "status": "pass",
                    "message": f"Valid API key - Credits: {credits}"
                })
            elif response.status_code == 402:
                results.append({
                    "name": "Remove.bg API",
                    "status": "pass",
                    "message": "Valid API key but quota exceeded"
                })
            else:
                results.append({
                    "name": "Remove.bg API",
                    "status": "fail",
                    "message": f"Invalid API key (Status: {response.status_code})"
                })
        else:
            results.append({
                "name": "Remove.bg API",
                "status": "fail",
                "message": "Missing API key"
            })
    except Exception as e:
        results.append({
            "name": "Remove.bg API",
            "status": "fail",
            "message": f"Error testing API: {str(e)}"
        })
    
    # Check if all tests passed
    all_passed = all(r['status'] == 'pass' for r in results)
    
    if all_passed:
        return jsonify({
            "message": "All tests passed!",
            "results": results
        })
    else:
        return jsonify({
            "error": "Some tests failed",
            "results": results
        }), 400


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
    
    # Get paper size selection (default to 4R)
    paper_type = request.form.get("paper_size", "4R")
    paper_info = get_paper_size(paper_type)
    paper_w, paper_h = paper_info['width'], paper_info['height']
    print(f"DEBUG: Using paper size: {paper_info['label']} ({paper_w}x{paper_h} pixels)")

    # Calculate optimal margins and gaps based on paper size
    # For 4R (1200x1800) with 390x480 photos: fit 3 per row
    photo_with_border_w = passport_width + 2 * border
    photo_with_border_h = passport_height + 2 * border
    
    # Calculate how many photos can fit in a row
    target_photos_per_row = 3 if paper_type == '4R' else 2
    horizontal_gap = 10
    margin_x = 10
    margin_y = 10
    
    # For 4R: optimize to fit exactly 3 photos per row
    if paper_type == '4R':
        # Photo with border: 390 + 2*2 = 394px
        # 3 photos: 3 * 394 = 1182px
        # Available space: 1200 - 1182 = 18px
        # 2 gaps + 2 margins = 18px
        # margin_x = 3, horizontal_gap = 6: 2*3 + 2*6 = 18px (perfect!)
        margin_x = 3
        horizontal_gap = 6
        spacing = 8  # Also reduce vertical spacing slightly
        print(f"DEBUG: Optimized 4R layout - margin_x={margin_x}, horizontal_gap={horizontal_gap}, spacing={spacing}")
        print(f"DEBUG: Calculation: 3*{photo_with_border_w} + 2*{horizontal_gap} + 2*{margin_x} = {3*photo_with_border_w + 2*horizontal_gap + 2*margin_x}px (paper width: {paper_w}px)")
    else:
        # Default spacing for other paper sizes
        horizontal_gap = 10
        margin_x = 10
        margin_y = 10

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
    current_page = Image.new("RGB", (paper_w, paper_h), "white")
    x, y = margin_x, margin_y

    def new_page():
        nonlocal current_page, x, y
        pages.append(current_page)
        current_page = Image.new("RGB", (paper_w, paper_h), "white")
        x, y = margin_x, margin_y

    for passport_img, copies in passport_images:
        for _ in range(copies):
            # Move to next row if needed
            if x + paste_w > paper_w - margin_x:
                x = margin_x
                y += paste_h + spacing

            # Move to next page if needed
            if y + paste_h > paper_h - margin_y:
                new_page()

            current_page.paste(passport_img, (x, y))
            print(f"DEBUG: Placed at x={x}, y={y}")
            x += paste_w + horizontal_gap

    pages.append(current_page)
    print(f"DEBUG: Total pages = {len(pages)}")
    print(f"DEBUG: Paper size: {paper_info['label']}, Photos per row: {target_photos_per_row}")

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