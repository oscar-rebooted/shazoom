from fastapi import FastAPI, UploadFile, File
from song_matcher import match_song
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs
import json

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Shazoom API is running"}

@app.post("/identify")
async def identify_song(file: UploadFile = File(...)):
    # Save uploaded file to temp location
    temp_path = "/tmp/uploaded_audio.mp3"
    with open(temp_path, "wb") as temp_file:
        content = await file.read()
        temp_file.write(content)
    
    # Process using your existing functions
    fingerprint = create_audio_fingerprint(temp_path)
    fingerprint_pairs = create_fingerprint_pairs(fingerprint)
    result = match_song(fingerprint_pairs)
    
    return result