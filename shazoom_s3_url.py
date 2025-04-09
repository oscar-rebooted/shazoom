import json
import boto3
import uuid
import os
from datetime import datetime

# Configure S3 client
s3_client = boto3.client('s3')
BUCKET_NAME = 'shazoom'  # Set this in Lambda environment variables

def lambda_handler(event, context):
    try:
        # Generate a unique file name
        file_key = f"samples/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4()}.mp3"
        
        conditions = [
            # Set file size limit to 20MB
            ["content-length-range", 0, 20971520]
        ]
        # Generate a presigned URL
        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=file_key,
            Conditions=conditions,
            ExpiresIn=300  # URL expires in 5 minutes
        )
        
        # Return the presigned URL and file key to the client
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',  # Update with your domain in production
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'uploadData': presigned_post,
                'fileKey': file_key
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }