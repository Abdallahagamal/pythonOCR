# api/extract.py

import os
import tempfile
import json
from main import extract_client
import jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "bO2dwe4+iEWyV2ntlMbCuf3SdNV4hW63v4EsEo3ovec=")

def handler(request):
    """Vercel expects a single entrypoint called 'handler'."""
    # Health check
    if request.method == "GET":
        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    # Token validation
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"statusCode": 401, "body": json.dumps({"message": "Token is missing"})}
    token = auth.split(" ")[1]
    try:
        jwt.decode(
            token,
            SECRET_KEY.encode("ascii"),
            algorithms=["HS256"],
            issuer="SecureApi",
            audience="SecureApiUser"
        )
    except jwt.ExpiredSignatureError:
        return {"statusCode": 401, "body": json.dumps({"message": "Token expired"})}
    except jwt.InvalidTokenError as e:
        return {"statusCode": 401, "body": json.dumps({"message": "Token invalid", "error": str(e)})}

    # Check file
    files = request.files or {}
    if "image" not in files:
        return {"statusCode": 400, "body": json.dumps({"message": "No file provided. Use key 'image'"})}
    
    file = files["image"]
    allowed = {"image/jpeg", "image/jpg", "image/png"}
    if file.content_type not in allowed:
        return {"statusCode": 400, "body": json.dumps({"message": "Only JPG and PNG allowed"})}

    temp_path = os.path.join(tempfile.gettempdir(), file.filename)
    file.save(temp_path)
    try:
        result = extract_client(temp_path)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": "Failed to process image", "error": str(e)})}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)