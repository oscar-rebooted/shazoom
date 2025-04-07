import json
import boto3
import os
os.environ['NUMBA_CACHE_DIR'] = '/tmp'
os.environ['LIBROSA_CACHE_DIR'] = '/tmp'

from song_matcher import match_song
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs

s3 = boto3.client('s3')
BUCKET_NAME = "shazoom"
TMP_DIR = '/tmp'

def lambda_handler(event, context):
    try:
        audio_path = "Reptilia.mp3"

        fingerprint = create_audio_fingerprint(audio_path)
        fingerprint_pairs, _ = create_fingerprint_pairs(fingerprint)

        os.makedirs(f"{TMP_DIR}/database", exist_ok=True)

        fingerprint_db_path = f'{TMP_DIR}/database/fingerprint_db.pkl'
        metadata_db_path = f'{TMP_DIR}/database/tracks_metadata.json'

        fingerprint_exists = os.path.exists(fingerprint_db_path)
        metadata_exists = os.path.exists(metadata_db_path)
        
        try:    
            if not fingerprint_exists:
                s3.download_file(BUCKET_NAME, 'fingerprint_db.pkl', fingerprint_db_path)
            if not metadata_exists:
                s3.download_file(BUCKET_NAME, 'tracks_metadata.json', metadata_db_path)
        except Exception as e:
            return {
                'statuscode': 500,
                'body': json.dumps({"error_type": "downloading db", "error": str(e)})
            }
        
        track_metadata, confidence, best_time_diff = match_song(fingerprint_pairs, db_dir=TMP_DIR)

        return {
            'statusCode': 200,
            'body': json.dumps({
                "message": "Song matching successful", 
                "track_metadata": track_metadata,
                "confidence": float(confidence)
                })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({"error": str(e)})
        }