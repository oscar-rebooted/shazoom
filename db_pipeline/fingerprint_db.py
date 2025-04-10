from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs, hash_function, quantize_value
import os
import pickle
import json
import re
import numpy as np
from tqdm import tqdm
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs, hash_function, quantize_value

def parse_metadata_from_filename(filename):
    basename = os.path.splitext(filename)[0]
    
    parts = basename.split(" - ", 1)
    
    if len(parts) == 2:
        artist, title = parts
    else:
        artist = "Unknown Artist"
        title = basename
    
    return artist, title

def create_fingerprint_database(mp3_folder, output_dir, target_peaks_per_second, target_zone_frames, window_length, hop_length, num_bands):
    os.makedirs(output_dir, exist_ok=True)
    
    mp3_files = [f for f in os.listdir(mp3_folder) if f.lower().endswith('.mp3')]
    
    if not mp3_files:
        print(f"No MP3 files found in {mp3_folder}")
        return
    
    print(f"Found {len(mp3_files)} MP3 files")
    
    metadata = {}
    
    database = {}
    
    for i, mp3_file in enumerate(mp3_files):
        track_id = i + 1
        file_path = os.path.join(mp3_folder, mp3_file)
        
        artist, title = parse_metadata_from_filename(mp3_file)
        
        metadata[track_id] = {
            "id": track_id,
            "title": title,
            "artist": artist,
            "filename": mp3_file
        }
        
        print(f"Processing {track_id}: {artist} - {title}")
        
        try:
            fingerprint = create_audio_fingerprint(
                file_path, 
                target_peaks_per_second=target_peaks_per_second,
                window_length=window_length, 
                hop_length=hop_length, 
                num_bands=num_bands
            )
            
            pairs, sorted_peaks = create_fingerprint_pairs(fingerprint, target_zone_frames)
            
            print(f"  Generated {len(pairs)} hash pairs from {len(fingerprint)} peaks")
                    
            for pair in pairs:
                freq1, freq2, delta_t, anchor_time = pair  # Unpack all 4 values
                
                freq_bin = 2
                time_bin = 2
                q_freq1 = quantize_value(freq1, freq_bin)
                q_freq2 = quantize_value(freq2, freq_bin)
                q_delta_t = quantize_value(delta_t, time_bin)
                
                hash_value = hash_function(q_freq1, q_freq2, q_delta_t)
                
                # Now we can use anchor_time directly rather than looking it up again
                if hash_value not in database:
                    database[hash_value] = []
                
                database[hash_value].append((track_id, anchor_time))
                
        except Exception as e:
            print(f"  Error processing {mp3_file}: {e}")
    
    pickle_path = os.path.join(output_dir, "fingerprint_db.pkl")
    with open(pickle_path, 'wb') as f:
        pickle.dump(database, f)
    
    json_database = {}
    for key, value in database.items():
        json_key = int(key) if hasattr(key, "item") else key
        json_value = []
        for track_id, time_offset in value:
            json_track_id = int(track_id) if hasattr(track_id, "item") else track_id
            json_time_offset = int(time_offset) if hasattr(time_offset, "item") else time_offset
            json_value.append((json_track_id, json_time_offset))
        json_database[str(json_key)] = json_value
    
    json_path = os.path.join(output_dir, "fingerprint_db.json")
    with open(json_path, 'w') as f:
        json.dump(json_database, f)
    
    json_metadata = {}
    for track_id, track_data in metadata.items():
        json_track_id = str(int(track_id) if hasattr(track_id, "item") else track_id)
        json_track_data = {}
        for k, v in track_data.items():
            if hasattr(v, "item"):
                json_track_data[k] = int(v) if isinstance(v, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64)) else float(v)
            else:
                json_track_data[k] = v
        json_metadata[json_track_id] = json_track_data
        
    metadata_path = os.path.join(output_dir, "tracks_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(json_metadata, f, ensure_ascii=False)
    
    print(f"\nDatabase created with {len(database)} unique hashes")
    print(f"Processed {len(metadata)} tracks")
    print(f"\nFiles saved to:")
    print(f"  Pickle database: {pickle_path}")
    print(f"  JSON database: {json_path}")
    print(f"  Tracks metadata: {metadata_path}")

if __name__ == "__main__":
    MP3_FOLDER = "./songs_mp3"
    OUTPUT_DIR = "./database"
    
    TARGET_PEAKS_PER_SECOND = 30
    TARGET_ZONE_FRAMES = 50
    WINDOW_LENGTH = 1024
    HOP_LENGTH = 32
    NUM_BANDS = 6
    
    create_fingerprint_database(
        mp3_folder=MP3_FOLDER,
        output_dir=OUTPUT_DIR,
        target_peaks_per_second=TARGET_PEAKS_PER_SECOND,
        target_zone_frames=TARGET_ZONE_FRAMES,
        window_length=WINDOW_LENGTH,
        hop_length=HOP_LENGTH,
        num_bands=NUM_BANDS
    )