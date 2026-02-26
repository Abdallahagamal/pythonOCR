from flask import Flask, request, jsonify
from functools import wraps
import jwt
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
extract_client = None
extractor_error = None

# Same secret key your .NET uses to sign JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "bO2dwe4+iEWyV2ntlMbCuf3SdNV4hW63v4EsEo3ovec=")


def get_extractor():
    global extract_client
    global extractor_error
    if extract_client is not None:
        return extract_client
    if extractor_error is not None:
        raise RuntimeError(extractor_error)
    try:
        from main import extract_client as extractor
        extract_client = extractor
        return extract_client
    except Exception as ex:
        extractor_error = f"Extractor initialization failed: {ex}"
        raise RuntimeError(extractor_error)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print("[DEBUG] Incoming headers:", dict(request.headers))
        auth = request.headers.get("Authorization", "")
        if not auth:
                # Vercel proxy sends JWT as X-Vercel-Proxy-Signature
                auth = request.headers.get("X-Vercel-Proxy-Signature", "")
        print("[DEBUG] Received token:", auth)
        if not auth.startswith("Bearer "):
            return jsonify({
                "message": "Token is missing",
                "headers": dict(request.headers)
            }), 401
        token = auth.split(" ")[1]
        try:
            secret = SECRET_KEY.encode("ascii")  # ← matches Encoding.ASCII.GetBytes()
            jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                issuer="SecureApi",        # ← matches Jwt:Issuer
                audience="SecureApiUser"   # ← matches Jwt:Audience
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"message": "Token is invalid", "error": str(e)}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "ok", "service": "python-ocr"}), 200


@app.route("/extract", methods=["POST"])
@token_required
def extract_route():
    if "image" not in request.files:
        return jsonify({"message": "No file provided. Use key 'image'"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    # Validate file type
    allowed = {"image/jpeg", "image/jpg", "image/png"}
    if file.content_type not in allowed:
        return jsonify({"message": "Only JPG and PNG allowed"}), 400

    # Save temporarily, process, then delete
    safe_name = secure_filename(file.filename) or "upload.jpg"
    temp_path = os.path.join(tempfile.gettempdir(), safe_name)
    file.save(temp_path)

    try:
        extractor = get_extractor()
        result = extractor(temp_path)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": "Failed to process image", "error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)