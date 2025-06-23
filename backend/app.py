import logging
from flask import Flask, request, jsonify, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
import requests
import json
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB connection settings
MONGO_HOST = os.getenv('MONGO_HOST', 'mongodb')
MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
MONGO_DB = os.getenv('MONGO_DB', 'mydb')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'user_input')

client_mongo = MongoClient(f'mongodb://{MONGO_HOST}:{MONGO_PORT}/')
db = client_mongo[MONGO_DB]
collection = db[MONGO_COLLECTION]

# Ollama API settings
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'ollama')
OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', 11434))
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"

SUPPORTED_MODELS = ["llama3", "mistral", "gemma:2b"]
DEFAULT_MODEL = "llama3"

@app.before_request
def log_request_info():
    logger.info(f"Request: {request.method} {request.path} - {request.remote_addr}")

@app.route('/api/submit', methods=['POST'])
def submit_text():
    data = request.json
    text_input = data.get('text')
    model = data.get('model', DEFAULT_MODEL)
    if model not in SUPPORTED_MODELS:
        model = DEFAULT_MODEL
    if not text_input:
        logger.warning('No text provided in /api/submit')
        return jsonify({'error': 'No text provided'}), 400
    try:
        # Call Ollama API synchronously (for storing in DB)
        payload = {
            "model": model,
            "prompt": text_input,
            "stream": False
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        response_json = resp.json()
        response_text = response_json["response"]
        doc = {
            'text_input': text_input,
            'gpt_response': response_text,
            'model': model,
            'created_at': datetime.utcnow()
        }
        result = collection.insert_one(doc)
        logger.info(f"Inserted text with id {result.inserted_id}")
        return jsonify({'message': 'Text and response saved successfully', 'id': str(result.inserted_id), 'gpt_response': response_text}), 201
    except Exception as e:
        logger.error(f"Error in /api/submit: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Database or Ollama error: {str(e)}'}), 500

@app.route('/api/stream_gpt', methods=['POST'])
def stream_gpt():
    data = request.json
    prompt = data.get('text')
    model = data.get('model', DEFAULT_MODEL)
    if model not in SUPPORTED_MODELS:
        model = DEFAULT_MODEL
    if not prompt:
        logger.warning('No prompt provided in /api/stream_gpt')
        return jsonify({'error': 'No prompt provided'}), 400
    
    # Store the complete response for saving to DB
    complete_response = ""
    
    def generate():
        nonlocal complete_response
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True
            }
            with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            if chunk.get('done'):
                                # Save the complete response to database
                                try:
                                    doc = {
                                        'text_input': prompt,
                                        'gpt_response': complete_response,
                                        'model': model,
                                        'created_at': datetime.utcnow()
                                    }
                                    result = collection.insert_one(doc)
                                    logger.info(f"Saved streaming response to DB with id {result.inserted_id}")
                                except Exception as db_error:
                                    logger.error(f"Error saving streaming response to DB: {db_error}")
                                
                                yield "data: [DONE]\n\n"
                                break
                            content = chunk.get('response', '')
                            if content:
                                complete_response += content
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except Exception as e:
                            logger.error(f"Error parsing Ollama stream chunk: {e}")
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error in /api/stream_gpt: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/texts', methods=['GET'])
def get_texts():
    try:
        docs = collection.find().sort('created_at', -1)
        texts = []
        for doc in docs:
            texts.append({
                'id': str(doc['_id']),
                'text': doc['text_input'],
                'gpt_response': doc.get('gpt_response', ''),
                'model': doc.get('model', DEFAULT_MODEL),
                'created_at': doc['created_at'].isoformat() + 'Z' if 'created_at' in doc else ''
            })
        logger.info(f"Fetched {len(texts)} texts from DB")
        return jsonify({'texts': texts}), 200
    except Exception as e:
        logger.error(f"Error in /api/texts GET: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/texts', methods=['DELETE'])
def delete_all_texts():
    try:
        result = collection.delete_many({})
        logger.info(f"Deleted {result.deleted_count} texts from DB")
        return jsonify({'message': f'Deleted {result.deleted_count} texts.'}), 200
    except Exception as e:
        logger.error(f"Error in /api/texts DELETE: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/texts/<text_id>', methods=['DELETE'])
def delete_text(text_id):
    try:
        result = collection.delete_one({'_id': ObjectId(text_id)})
        if result.deleted_count == 1:
            logger.info(f"Deleted text with id {text_id}")
            return jsonify({'message': 'Text deleted.'}), 200
        else:
            logger.warning(f"Text with id {text_id} not found for deletion")
            return jsonify({'error': 'Text not found.'}), 404
    except Exception as e:
        logger.error(f"Error in /api/texts/<id> DELETE: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    logger.info("Health check requested")
    return jsonify({'status': 'healthy'}), 200

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}\n{traceback.format_exc()}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 Not Found: {request.path}")
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=False)
