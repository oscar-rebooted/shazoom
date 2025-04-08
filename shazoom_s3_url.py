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
        print(file_key)
        # Generate a presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_key,
                'ContentType': 'audio/mpeg'
            },
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
                'uploadUrl': presigned_url,
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