import json
import boto3
import os
os.environ['NUMBA_CACHE_DIR'] = '/tmp'
os.environ['LIBROSA_CACHE_DIR'] = '/tmp'

from song_matcher import match_song
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs

# Initialise container
s3 = boto3.client('s3')
BUCKET_NAME = "shazoom"
TMP_DIR = '/tmp'
os.makedirs(f'{TMP_DIR}/samples', exist_ok=True)

# Get databases
os.makedirs(f'{TMP_DIR}/databases', exist_ok=True)

db_path_fingerprint = "databases/fingerprint_db.pkl"
db_path_metadata = "databases/tracks_metadata.json"

db_path_fingerprint_local = f'{TMP_DIR}/{db_path_fingerprint}'
db_path_metadata_local = f'{TMP_DIR}/{db_path_metadata}'

s3.download_file(BUCKET_NAME, db_path_fingerprint, db_path_fingerprint_local)
s3.download_file(BUCKET_NAME, db_path_metadata, db_path_metadata_local)

def lambda_handler(event, context):
    try:
        # Get audio sample
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
        
        s3_audio_path = body['fileKey']
        audio_path = f"{TMP_DIR}/{s3_audio_path}"

        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        s3.download_file(BUCKET_NAME, s3_audio_path, audio_path)
    
        # Search database with sample
        fingerprint = create_audio_fingerprint(audio_path)
        fingerprint_pairs, _ = create_fingerprint_pairs(fingerprint)

        track_metadata, confidence, best_time_diff = match_song(fingerprint_pairs, db_path_fingerprint_local, db_path_metadata_local)

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                "message": "Song matching successful", 
                "track_metadata": track_metadata,
                "confidence": float(confidence)
                })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({"error": str(e)})
        }