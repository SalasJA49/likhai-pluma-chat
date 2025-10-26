import uuid
def generate_response(message, model=None):
    # stub — replace with real provider later
    return {"chat_id": str(uuid.uuid4()), "text": "This is a stub response to: "+message}