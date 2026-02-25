from flask import Flask, request, jsonify
from functools import wraps
import jwt
import base64
import os
import tempfile
from main import extract_client

app = Flask(__name__)

# Same secret key your .NET uses to sign JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "bO2dwe4+iEWyV2ntlMbCuf3SdNV4hW63v4EsEo3ovec=")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "Token is missing"}), 401
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
    temp_path = os.path.join(tempfile.gettempdir(), file.filename)
    file.save(temp_path)

    try:
        result = extract_client(temp_path)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": "Failed to process image", "error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)