FROM public.ecr.aws/lambda/python:3.12

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Install the function's dependencies
RUN pip install numpy==2.1.3 scipy==1.15.2 librosa==0.11.0 boto3==1.37.23

# Copy function code
COPY lambda_handler.py .
COPY audio_fingerprint.py .
COPY song_matcher.py .

# Create database directory
RUN mkdir -p ./database

# Copy sample data for local testing
# COPY database/fingerprint_db.pkl ./database/
# COPY database/tracks_metadata.json ./database/
COPY Reptilia.mp3 .

# Verify files were copied (for debugging)
RUN ls -la ${LAMBDA_TASK_ROOT}
RUN ls -la ${LAMBDA_TASK_ROOT}/database

# Set the CMD to your handler
CMD [ "lambda_handler.lambda_handler" ]