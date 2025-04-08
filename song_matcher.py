import pickle
import json
from audio_fingerprint import get_nearby_hashes

db_fingerprint = None
db_metadata = None

def load_databases(db_path_fingerprint="databases/fingerprint_db.pkl", db_path_metadata="databases/tracks_metadata.json"):
    global db_fingerprint, db_metadata
    
    if not db_fingerprint:  
        with open(db_path_fingerprint, 'rb') as f:
            db_fingerprint = pickle.load(f)
    if not db_metadata:
        with open(db_path_metadata, 'r', encoding='utf-8') as f:
            db_metadata = json.load(f)
    
    return db_fingerprint, db_metadata

def match_song(fingerprint_pairs, db_path_fingerprint, db_path_metadata):
    db, metadata = load_databases(db_path_fingerprint, db_path_metadata)
    
    match_counts = {}
    
    # For tracking which query hashes matched which tracks
    matched_hashes = {}  # {track_id: set(query_hash_indices)}
    
    # Parameters for locality sensitive hashing
    freq_bin = 2
    time_bin = 2
    
    total_lookups = 0
    total_matches = 0
    
    print(f"Looking up {len(fingerprint_pairs)} fingerprint pairs...")
    
    for idx, (freq1, freq2, delta_t, query_time) in enumerate(fingerprint_pairs):
        total_lookups += 1
        
        # Generate a list of potential hash variants
        nearby_hashes = get_nearby_hashes(freq1, freq2, delta_t, freq_bin, time_bin)
        
        # Look up each hash variant in the database
        for hash_value in nearby_hashes:
            if hash_value in db:
                for track_id, db_time in db[hash_value]:
                    # Calculate time difference between query and database
                    time_diff = query_time - db_time
                    
                    # Bin time differences to account for small timing variations
                    binned_time_diff = (time_diff // 3) * 3
                    
                    # Initialize track in match_counts if not present
                    if track_id not in match_counts:
                        match_counts[track_id] = {}
                        matched_hashes[track_id] = set()
                    
                    # Update match count
                    match_counts[track_id][binned_time_diff] = match_counts[track_id].get(binned_time_diff, 0) + 1
                    
                    # Record that this query hash matched this track
                    matched_hashes[track_id].add(idx)
                    
                    total_matches += 1
        
        # Print a dot for progress visualization every 100 pairs
        if total_lookups % 100 == 0:
            print(".", end="", flush=True)
    
    print(f"\nFound {total_matches} matches from {total_lookups} lookups")
    
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
    
    # Calculate confidence as (number of hashes that matched the best track) / (total number of hashes in query)
    unique_hash_matches = len(matched_hashes.get(best_track_id, set()))
    confidence = unique_hash_matches / len(fingerprint_pairs) if fingerprint_pairs else 0
    
    print(f"Best track had {unique_hash_matches} unique matching hashes out of {len(fingerprint_pairs)} query hashes")
    print(f"Peak alignment count: {best_count}")
    print(f"Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
    
    # Get track metadata
    track_metadata = None
    if best_track_id is not None:
        # Convert to string since JSON keys are strings
        track_metadata = metadata.get(str(best_track_id))
    
    return track_metadata, confidence, best_time_diff

def main(fingerprint_pairs):
    track_metadata, confidence, time_diff = match_song(fingerprint_pairs)
    
    return {
        'track': track_metadata,
        'confidence': confidence,
        'time_offset': time_diff,
        'message': f"Best match: '{track_metadata['title']}' by {track_metadata['artist']}" if track_metadata else "No strong matches found"
    }