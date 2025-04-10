import os
import json
import pickle
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs, hash_function, quantize_value

def load_metadata(json_path):
    """Load the Spotify metadata from JSON file"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_existing_database(pickle_path):
    """Load existing fingerprint database from pickle file"""
    try:
        with open(pickle_path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print(f"No existing database found at {pickle_path}. Creating new database.")
        return {}

def save_database(database, pickle_path):
    """Save the updated database to pickle file"""
    with open(pickle_path, 'wb') as f:
        pickle.dump(database, f)
    print(f"Database saved to {pickle_path}")

def process_track(file_path, track_id, database, fingerprint_params):
    """Process a single track and add its fingerprints to the database"""
    try:
        fingerprint = create_audio_fingerprint(
            file_path, 
            target_peaks_per_second=fingerprint_params["target_peaks_per_second"],
            window_length=fingerprint_params["window_length"], 
            hop_length=fingerprint_params["hop_length"], 
            num_bands=fingerprint_params["num_bands"]
        )
        
        pairs, sorted_peaks = create_fingerprint_pairs(fingerprint, fingerprint_params["target_zone_frames"])
        
        print(f"  Generated {len(pairs)} hash pairs from {len(fingerprint)} peaks")
        
        fingerprint_count = 0
        for pair in pairs:
            freq1, freq2, delta_t, anchor_time = pair
            
            freq_bin = 2
            time_bin = 2
            q_freq1 = quantize_value(freq1, freq_bin)
            q_freq2 = quantize_value(freq2, freq_bin)
            q_delta_t = quantize_value(delta_t, time_bin)
            
            hash_value = hash_function(q_freq1, q_freq2, q_delta_t)
            
            if hash_value not in database:
                database[hash_value] = []
            
            database[hash_value].append((track_id, anchor_time))
            fingerprint_count += 1
        
        return fingerprint_count
    except Exception as e:
        print(f"  Error processing track: {e}")
        return 0

def append_fingerprints(metadata_path, downloads_folder, pickle_path, fingerprint_params):
    """Main function to append fingerprints to existing database"""
    # Load metadata and existing database
    metadata = load_metadata(metadata_path)
    database = load_existing_database(pickle_path)
    
    # Get existing tracks to avoid duplicate processing
    existing_track_ids = set()
    for hash_value in database:
        for track_id, _ in database[hash_value]:
            existing_track_ids.add(track_id)
    
    # Process each track in the metadata
    total_added = 0
    for track_id, track_data in metadata.items():        
        # Skip if already processed
        if track_id in existing_track_ids:
            print(f"Skipping track_id {track_id} ({track_data.get('artist', '')} - {track_data.get('spotify_title', '')}): Already processed")
            continue
            
        original_filename = track_data.get("original_filename", "")
        if not original_filename:
            print(f"Skipping track_id {track_id}: No original filename")
            continue
            
        # Build file path directly as original_filename now includes the extension
        file_path = os.path.join(downloads_folder, original_filename)
        if not os.path.exists(file_path):
            print(f"Skipping track_id {track_id}: File not found at '{file_path}'")
            continue
            
        # Process the track
        print(f"Processing track_id {track_id}: {track_data.get('artist', '')} - {track_data.get('spotify_title', '')}")
        fingerprint_count = process_track(file_path, track_id, database, fingerprint_params)
        
        if fingerprint_count > 0:
            total_added += 1
            print(f"  Added {fingerprint_count} fingerprints for track_id {track_id}")
        
        # Save after each track to prevent data loss
        save_database(database, pickle_path)
        
    print(f"\nProcessing complete: Added {total_added} new tracks to the database")
    print(f"Final database contains {sum(len(entries) for entries in database.values())} fingerprint entries")
    print(f"Total unique tracks in database: {len(existing_track_ids) + total_added}")

if __name__ == "__main__":
    # Configuration
    METADATA_PATH = "metadata_spotify.json"
    DOWNLOADS_FOLDER = "downloads"  
    PICKLE_PATH = "fingerprint_db.pkl"
    
    # Fingerprinting parameters (same as in original script)
    FINGERPRINT_PARAMS = {
        "target_peaks_per_second": 30,
        "target_zone_frames": 50,
        "window_length": 1024,
        "hop_length": 32,
        "num_bands": 6
    }
    
    append_fingerprints(METADATA_PATH, DOWNLOADS_FOLDER, PICKLE_PATH, FINGERPRINT_PARAMS)