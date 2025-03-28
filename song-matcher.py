import os
import pickle
import json
import time
import boto3

# Global variable to store the database and metadata
fingerprint_db = None
tracks_metadata = None
db_last_loaded = 0
DB_CACHE_DURATION = 3600  # Reload DB every hour

def load_databases():
    """
    Load fingerprint database and track metadata from S3 or local cache
    """
    global fingerprint_db, tracks_metadata, db_last_loaded
    
    # Check if we need to reload the database
    current_time = time.time()
    if fingerprint_db is not None and tracks_metadata is not None and current_time - db_last_loaded < DB_CACHE_DURATION:
        return fingerprint_db, tracks_metadata
    
    # Check if database is cached in /tmp
    fingerprint_tmp = "/tmp/fingerprint_db.pkl"
    metadata_tmp = "/tmp/tracks_metadata.json"
    
    # Check if cached files exist and are recent
    fingerprint_cached = os.path.exists(fingerprint_tmp) and current_time - os.path.getmtime(fingerprint_tmp) < DB_CACHE_DURATION
    metadata_cached = os.path.exists(metadata_tmp) and current_time - os.path.getmtime(metadata_tmp) < DB_CACHE_DURATION
    
    # Load fingerprint database
    if fingerprint_cached:
        with open(fingerprint_tmp, 'rb') as f:
            fingerprint_db = pickle.load(f)
    else:
        # Download from S3
        s3 = boto3.client('s3')
        s3.download_file('your-bucket', 'fingerprint_db.pkl', fingerprint_tmp)
        
        # Load into memory
        with open(fingerprint_tmp, 'rb') as f:
            fingerprint_db = pickle.load(f)
    
    # Load track metadata
    if metadata_cached:
        with open(metadata_tmp, 'r') as f:
            tracks_metadata = json.load(f)
    else:
        # Download from S3
        s3 = boto3.client('s3')
        s3.download_file('your-bucket', 'tracks_metadata.json', metadata_tmp)
        
        # Load into memory
        with open(metadata_tmp, 'r') as f:
            tracks_metadata = json.load(f)
    
    db_last_loaded = current_time
    return fingerprint_db, tracks_metadata

def match_song(fingerprint_pairs):
    """
    Find the best matching song for the given fingerprint pairs.
    
    Args:
        fingerprint_pairs: List of (freq1, freq2, delta_t, query_time) tuples
    
    Returns:
        (track_metadata, confidence_score)
    """
    # Load databases
    db, metadata = load_databases()
    
    # Track matches by song and time offset
    match_counts = {}  # {track_id: {time_diff: count}}
    
    # For each fingerprint pair in the query
    for freq1, freq2, delta_t, query_time in fingerprint_pairs:
        # Create hash
        hash_value = hash_function(freq1, freq2, delta_t)
        
        # Look up in database
        if hash_value in db:
            # For each potential matching track that has this hash
            for track_id, db_time in db[hash_value]:
                # Calculate time difference
                time_diff = query_time - db_time
                
                # Initialize counters if needed
                if track_id not in match_counts:
                    match_counts[track_id] = {}
                if time_diff not in match_counts[track_id]:
                    match_counts[track_id][time_diff] = 0
                
                # Increment match count
                match_counts[track_id][time_diff] += 1
    
    # Find track with highest count for any time difference
    best_track_id = None
    best_count = 0
    best_time_diff = None
    
    for track_id, time_diffs in match_counts.items():
        track_max_count = max(time_diffs.values()) if time_diffs else 0
        if track_max_count > best_count:
            best_count = track_max_count
            best_track_id = track_id
            best_time_diff = max(time_diffs.items(), key=lambda x: x[1])[0]
    
    # Calculate confidence
    confidence = best_count / len(fingerprint_pairs) if fingerprint_pairs else 0
    
    # Get track metadata
    track_metadata = None
    if best_track_id is not None:
        # Convert to string since JSON keys are strings
        track_metadata = metadata.get(str(best_track_id))
    
    return track_metadata, confidence, best_time_diff

def hash_function(freq1, freq2, delta_t):
    """
    Create a compact hash from the fingerprint components.
    Assumes freq1, freq2 are 10-bit values and delta_t is a 10-bit value.
    """
    # Pack into a 32-bit integer
    # Use bit shifting to compose the hash
    return (freq1 << 20) | (freq2 << 10) | delta_t

def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    
    Args:
        event: Should contain the fingerprint_pairs for matching
        
    Returns:
        The matched song and confidence score
    """
    # Extract fingerprint pairs from event
    fingerprint_pairs = event.get('fingerprint_pairs', [])
    
    # Match song
    track_metadata, confidence, time_diff = match_song(fingerprint_pairs)
    
    # Return result
    if track_metadata:
        return {
            'match_found': True,
            'track': track_metadata,
            'confidence': confidence,
            'time_offset': time_diff,
            'message': f"Matched '{track_metadata['title']}' by {track_metadata['artist']} with {confidence:.2f} confidence"
        }
    else:
        return {
            'match_found': False,
            'confidence': confidence,
            'message': "No matching song found"
        }
