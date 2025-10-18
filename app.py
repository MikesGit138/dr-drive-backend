# from flask import Flask, request, jsonify
# import anthropic
# import base64
# import os
# from pathlib import Path
#
# app = Flask(__name__)
#
# # Mock database for client details - replace with real database
# CLIENT_DATABASE = {
#     "C001": {
#         "name": "John Doe",
#         "cars": [
#             {
#                 "id": "CAR001",
#                 "make": "Toyota",
#                 "model": "Camry",
#                 "year": 2019,
#                 "chassis_number": "4T1BF1AK5CU123456"
#             }
#         ]
#     },
#     "C002": {
#         "name": "Jane Smith",
#         "cars": [
#             {
#                 "id": "CAR002",
#                 "make": "Honda",
#                 "model": "Civic",
#                 "year": 2021,
#                 "chassis_number": "2HGCV52651H123456"
#             }
#         ]
#     }
# }
#
# def get_client_details(client_id):
#     """Fetch client details from database"""
#     return CLIENT_DATABASE.get(client_id, None)
#
#
# def encode_file_to_base64(file_path):
#     """Convert file to base64 for API submission"""
#     with open(file_path, "rb") as file:
#         return base64.standard_b64encode(file.read()).decode("utf-8")
#
#
# def get_media_type(file_path):
#     """Determine media type based on file extension"""
#     extension = Path(file_path).suffix.lower()
#     media_types = {
#         ".jpg": "image/jpeg",
#         ".jpeg": "image/jpeg",
#         ".png": "image/png",
#         ".gif": "image/gif",
#         ".webp": "image/webp",
#         ".mp4": "video/mp4",
#         ".mpeg": "video/mpeg",
#         ".mov": "video/quicktime",
#         ".mp3": "audio/mpeg",
#         ".wav": "audio/wav",
#         ".m4a": "audio/mp4"
#     }
#     return media_types.get(extension, "application/octet-stream")
#
#
# def build_diagnostic_prompt(client_details, car_id, text_description):
#     """Build the prompt with client and car information"""
#     car = next((c for c in client_details["cars"] if c["id"] == car_id), None)
#
#     if not car:
#         return None
#
#     prompt = f"""You are an experienced mechanic. A customer has come to you with the following issue:
#
# Customer Name: {client_details['name']}
# Vehicle Make: {car['make']}
# Vehicle Model: {car['model']}
# Vehicle Year: {car['year']}
# Chassis Number: {car['chassis_number']}
#
# Customer's Description of the Problem:
# {text_description}
#
# Based on the customer's description and any visual/audio/video evidence provided, please provide:
#
# 1. **Diagnosis**: Identify the likely problem(s) with the vehicle
# 2. **Suggested Solution**: Provide recommended repairs or maintenance
# 3. **Part Numbers**: If replacement parts are needed, provide the part numbers and names
#
# Format your response as follows:
# DIAGNOSIS: [Your diagnosis here]
# SUGGESTED_SOLUTION: [Your solution here]
# PARTS_REQUIRED: [List parts with part numbers, or "None" if no parts needed]"""
#
#     return prompt
# @app.route("/", methods=["GET", "POST"])
# def index():
#     return 'hello world'
#
# @app.route("/diagnose", methods=["POST"])
# def diagnose():
#     """Main endpoint for vehicle diagnosis"""
#     try:
#         # Extract data from request
#         client_id = request.form.get("client_id")
#         car_id = request.form.get("car_id")
#         text_description = request.form.get("text_description")
#
#         # Validate required fields
#         if not client_id or not car_id or not text_description:
#             return jsonify({
#                 "error": "Missing required fields: client_id, car_id, text_description"
#             }), 400
#
#         # Get client details
#         client_details = get_client_details(client_id)
#         if not client_details:
#             return jsonify({"error": f"Client {client_id} not found"}), 404
#
#         # Build the prompt
#         prompt = build_diagnostic_prompt(client_details, car_id, text_description)
#         if not prompt:
#             return jsonify({"error": f"Car {car_id} not found for client {client_id}"}), 404
#
#         # Prepare content for Claude API
#         content = [
#             {
#                 "type": "text",
#                 "text": prompt
#             }
#         ]
#
#         # Process audio file if provided
#         if "audio" in request.files:
#             audio_file = request.files["audio"]
#             audio_path = f"/tmp/{audio_file.filename}"
#             audio_file.save(audio_path)
#
#             audio_data = encode_file_to_base64(audio_path)
#             content.append({
#                 "type": "audio",
#                 "media_type": "audio/mp3",
#                 "data": audio_data
#             })
#             os.remove(audio_path)
#
#         # Process image file if provided
#         if "image" in request.files:
#             image_file = request.files["image"]
#             image_path = f"/tmp/{image_file.filename}"
#             image_file.save(image_path)
#
#             image_data = encode_file_to_base64(image_path)
#             media_type = get_media_type(image_path)
#             content.append({
#                 "type": "image",
#                 "media_type": media_type,
#                 "data": image_data
#             })
#             os.remove(image_path)
#
#         # Process video file if provided
#         if "video" in request.files:
#             video_file = request.files["video"]
#             video_path = f"/tmp/{video_file.filename}"
#             video_file.save(video_path)
#
#             video_data = encode_file_to_base64(video_path)
#             media_type = get_media_type(video_path)
#             content.append({
#                 "type": "video",
#                 "media_type": media_type,
#                 "data": video_data
#             })
#             os.remove(video_path)
#
#         # Send to Claude API
#         client = anthropic.Anthropic()
#         message = client.messages.create(
#             model="claude-3-5-sonnet-20241022",
#             max_tokens=1024,
#             messages=[
#                 {
#                     "role": "user",
#                     "content": content
#                 }
#             ]
#         )
#
#         # Parse response
#         response_text = message.content[0].text
#
#         # Extract structured data from response
#         diagnosis = ""
#         suggested_solution = ""
#         parts_required = ""
#
#         lines = response_text.split("\n")
#         for i, line in enumerate(lines):
#             if line.startswith("DIAGNOSIS:"):
#                 diagnosis = line.replace("DIAGNOSIS:", "").strip()
#             elif line.startswith("SUGGESTED_SOLUTION:"):
#                 suggested_solution = line.replace("SUGGESTED_SOLUTION:", "").strip()
#             elif line.startswith("PARTS_REQUIRED:"):
#                 parts_required = line.replace("PARTS_REQUIRED:", "").strip()
#
#         return jsonify({
#             "client_id": client_id,
#             "car_id": car_id,
#             "vehicle_info": {
#                 "make": client_details["cars"][0]["make"],
#                 "model": client_details["cars"][0]["model"],
#                 "year": client_details["cars"][0]["year"],
#                 "chassis_number": client_details["cars"][0]["chassis_number"]
#             },
#             "diagnosis": diagnosis,
#             "suggested_solution": suggested_solution,
#             "parts_required": parts_required if parts_required != "None" else None,
#             "raw_response": response_text
#         }), 200
#
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
#
#
# @app.route("/health", methods=["GET"])
# def health():
#     """Health check endpoint"""
#     return jsonify({"status": "OK"}), 200
#
#
# if __name__ == "__main__":
#     app.run(debug=True, port=5000)