import os
import pickle
import json
import re
import numpy as np
import librosa
import scipy.ndimage
from tqdm import tqdm

def create_audio_fingerprint(audio_path, target_peaks_per_second, window_length, hop_length, num_bands):
    # 1. Load and preprocess the audio
    y, sr = librosa.load(audio_path, mono=True, sr=8192)
    
    # 2. Compute STFT
    D = librosa.stft(y, n_fft=window_length, hop_length=hop_length)
    
    # 3. Compute magnitude spectrogram
    magnitude = np.abs(D)
    
    # 4. Divide frequency bins into logarithmic bands
    freq_bins = magnitude.shape[0]
    bands = []
    
    band_edges = np.logspace(np.log10(1), np.log10(freq_bins-1), num_bands + 1).astype(int)
    band_edges[0] = 0
    
    for i in range(num_bands):
        start = band_edges[i]
        end = band_edges[i + 1]
        bands.append((start, end))
    
    # 5. For each time frame and each frequency band, find the maximum
    band_peaks = np.zeros_like(magnitude)
    
    for t in range(magnitude.shape[1]):
        for start, end in bands:
            band_magnitude = magnitude[start:end, t]
            
            if len(band_magnitude) > 0:
                max_idx = np.argmax(band_magnitude) + start
                band_peaks[max_idx, t] = magnitude[max_idx, t]
    
    # 6. Apply max filter to identify local peaks with dynamic neighbourhood size
    duration = len(y) / sr
    total_desired_peaks = int(duration * target_peaks_per_second)
    neighbourhood_size = 30
    
    # Binary search to find appropriate neighbourhood size
    min_size = 5
    max_size = 100
    peak_mask = None
    
    while min_size <= max_size:
        neighbourhood_size = (min_size + max_size) // 2
        max_filtered = scipy.ndimage.maximum_filter(band_peaks, size=(neighbourhood_size, neighbourhood_size))
        peak_mask = (band_peaks == max_filtered) & (band_peaks > 0)
        num_peaks = np.sum(peak_mask)
        
        if num_peaks > total_desired_peaks * 1.2:  # Too many peaks
            min_size = neighbourhood_size + 1
        elif num_peaks < total_desired_peaks * 0.8:  # Too few peaks
            max_size = neighbourhood_size - 1
        else:
            break
    
    # If we didn't find a good size, use the last one tried
    if peak_mask is None:
        neighbourhood_size = 30
        max_filtered = scipy.ndimage.maximum_filter(band_peaks, size=(neighbourhood_size, neighbourhood_size))
        peak_mask = (band_peaks == max_filtered) & (band_peaks > 0)
    
    print(f"  Using neighbourhood size: {neighbourhood_size}")
    print(f"  Number of peaks found: {np.sum(peak_mask)}")
    print(f"  Target number of peaks: {total_desired_peaks}")
    
    # 7. Get the coordinates of all peak points
    peak_coordinates = np.argwhere(peak_mask)
    
    # Convert to list of (time, frequency) tuples for the fingerprint
    fingerprint = [(time, freq) for freq, time in peak_coordinates]
    
    return fingerprint

def create_fingerprint_pairs(fingerprint, target_zone_frames):
    pairs = []
    
    # Sort peaks by time
    sorted_peaks = sorted(fingerprint, key=lambda x: x[0])
    
    # Create pairs
    for i, anchor_point in enumerate(sorted_peaks):
        anchor_time, anchor_freq = anchor_point
        
        # Look at peaks within target zone
        for j in range(i+1, len(sorted_peaks)):
            target_point = sorted_peaks[j]
            target_time, target_freq = target_point
            
            # Check if the target point is within the target zone
            time_diff = target_time - anchor_time
            if time_diff > target_zone_frames:
                break
                
            # Create pair
            pair = (anchor_freq, target_freq, time_diff)
            pairs.append(pair)
    
    return pairs, sorted_peaks

def hash_function(freq1, freq2, delta_t):
    # Pack into a 32-bit integer using bit shifting
    return (freq1 << 20) | (freq2 << 10) | delta_t

def parse_metadata_from_filename(filename):
    # Remove file extension
    basename = os.path.splitext(filename)[0]
    
    # Split by " - " to get artist and title
    parts = basename.split(" - ", 1)
    
    if len(parts) == 2:
        artist, title = parts
    else:
        # If filename doesn't match expected format, use filename as title
        artist = "Unknown Artist"
        title = basename
    
    return artist, title

def create_fingerprint_database(mp3_folder, output_dir, target_peaks_per_second, target_zone_frames, window_length, hop_length, num_bands):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get list of MP3 files
    mp3_files = [f for f in os.listdir(mp3_folder) if f.lower().endswith('.mp3')]
    
    if not mp3_files:
        print(f"No MP3 files found in {mp3_folder}")
        return
    
    print(f"Found {len(mp3_files)} MP3 files")
    
    # Dictionary to store track metadata
    metadata = {}
    
    # Database dictionary for fingerprints
    database = {}  # {hash_value: [(track_id, time_offset), ...]}
    
    # Process each file
    for i, mp3_file in enumerate(mp3_files):
        track_id = i + 1  # Track IDs start from 1
        file_path = os.path.join(mp3_folder, mp3_file)
        
        # Extract metadata from filename
        artist, title = parse_metadata_from_filename(mp3_file)
        
        # Store metadata
        metadata[track_id] = {
            "id": track_id,
            "title": title,
            "artist": artist,
            "filename": mp3_file
        }
        
        print(f"Processing {track_id}: {artist} - {title}")
        
        # Extract fingerprint
        try:
            fingerprint = create_audio_fingerprint(file_path, target_peaks_per_second, 
                                                  window_length, hop_length, num_bands)
            
            # Generate fingerprint pairs
            pairs, sorted_peaks = create_fingerprint_pairs(fingerprint, target_zone_frames)
            
            print(f"  Generated {len(pairs)} hash pairs from {len(fingerprint)} peaks")
            
            # Add to database
            for pair in pairs:
                freq1, freq2, delta_t = pair
                hash_value = hash_function(freq1, freq2, delta_t)
                
                # Find the corresponding anchor point time
                anchor_time = None
                for peak in sorted_peaks:
                    if peak[1] == freq1:  # If frequency matches
                        anchor_time = peak[0]
                        break
                
                if anchor_time is not None:
                    if hash_value not in database:
                        database[hash_value] = []
                    
                    database[hash_value].append((track_id, anchor_time))
        
        except Exception as e:
            print(f"  Error processing {mp3_file}: {e}")
    
    # Save database to pickle file
    pickle_path = os.path.join(output_dir, "fingerprint_db.pkl")
    with open(pickle_path, 'wb') as f:
        pickle.dump(database, f)
    
    # Convert database to JSON-compatible format
    # Convert numpy int64 values to regular Python ints for JSON compatibility
    json_database = {}
    for key, value in database.items():
        # Convert key from int64 to regular int if needed
        json_key = int(key) if hasattr(key, "item") else key
        # Convert values in the list of tuples
        json_value = []
        for track_id, time_offset in value:
            # Convert from int64/numpy types to regular Python int
            json_track_id = int(track_id) if hasattr(track_id, "item") else track_id
            json_time_offset = int(time_offset) if hasattr(time_offset, "item") else time_offset
            json_value.append((json_track_id, json_time_offset))
        json_database[str(json_key)] = json_value
    
    # Save database to JSON file
    json_path = os.path.join(output_dir, "fingerprint_db.json")
    with open(json_path, 'w') as f:
        json.dump(json_database, f)
    
    # Convert metadata to ensure all values are JSON serializable
    json_metadata = {}
    for track_id, track_data in metadata.items():
        json_track_id = str(int(track_id) if hasattr(track_id, "item") else track_id)
        # Convert all values to ensure they're JSON serializable
        json_track_data = {}
        for k, v in track_data.items():
            if hasattr(v, "item"):  # Check if it's a numpy type
                json_track_data[k] = int(v) if isinstance(v, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64)) else float(v)
            else:
                json_track_data[k] = v
        json_metadata[json_track_id] = json_track_data
        
    # Save metadata to JSON file
    metadata_path = os.path.join(output_dir, "tracks_metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(json_metadata, f)
    
    print(f"\nDatabase created with {len(database)} unique hashes")
    print(f"Processed {len(metadata)} tracks")
    print(f"\nFiles saved to:")
    print(f"  Pickle database: {pickle_path}")
    print(f"  JSON database: {json_path}")
    print(f"  Tracks metadata: {metadata_path}")

if __name__ == "__main__":
    # Key parameters for the fingerprinting algorithm
    MP3_FOLDER = "./songs_mp3"
    OUTPUT_DIR = "./database"
    
    # Audio fingerprinting parameters
    TARGET_PEAKS_PER_SECOND = 30
    TARGET_ZONE_FRAMES = 50
    WINDOW_LENGTH = 1024
    HOP_LENGTH = 32
    NUM_BANDS = 6
    
    # Create the fingerprint database
    create_fingerprint_database(
        mp3_folder=MP3_FOLDER,
        output_dir=OUTPUT_DIR,
        target_peaks_per_second=TARGET_PEAKS_PER_SECOND,
        target_zone_frames=TARGET_ZONE_FRAMES,
        window_length=WINDOW_LENGTH,
        hop_length=HOP_LENGTH,
        num_bands=NUM_BANDS
    )