import json
import boto3
import os
from song_matcher import match_song
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs

s3 = boto3.client('s3')
BUCKET_NAME = "shazoom"

def lambda_handler(event, context):
    # Get the uploaded audio file from the event
    # This depends on how you trigger the Lambda (API Gateway, S3 event, etc.)
    
    # Example for API Gateway with base64 encoded audio
    if 'body' in event:
        # request_body = json.loads(event['body'])
        # audio_data = base64.b64decode(request_body['audio_data'])
        
        # Save temporary audio file
        temp_audio_path = 'Reptilia.mp3'
        # with open(temp_audio_path, 'wb') as f:
        #     f.write(audio_data)
        
        # Process audio and match
        fingerprint = create_audio_fingerprint(temp_audio_path)
        fingerprint_pairs, _ = create_fingerprint_pairs(fingerprint)
        
        # Download database files if needed
        fingerprint_exists = os.path.exists('fingerprint_db.pkl')
        metadata_exists = os.path.exists('tracks_metadata.json')
        
        if not fingerprint_exists:
            s3.download_file(BUCKET_NAME, 'fingerprint_db.pkl', './fingerprint_db.pkl')
        if not metadata_exists:
            s3.download_file(BUCKET_NAME, 'tracks_metadata.json', './tracks_metadata.json')
        
        # Match the song
        result = match_song(fingerprint_pairs)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    
    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Invalid request format'})
    }