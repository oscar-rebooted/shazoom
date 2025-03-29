import os
import pickle
import json
import time
import matplotlib.pyplot as plt
from audio_fingerprint import create_audio_fingerprint, create_fingerprint_pairs, hash_function, get_nearby_hashes, quantize_value

fingerprint_db = None
tracks_metadata = None
db_last_loaded = 0
DB_CACHE_DURATION = 3600

def load_databases():
    global fingerprint_db, tracks_metadata, db_last_loaded
    
    current_time = time.time()
    if fingerprint_db is not None and tracks_metadata is not None and current_time - db_last_loaded < DB_CACHE_DURATION:
        return fingerprint_db, tracks_metadata
    
    fingerprint_path = "./database/fingerprint_db.pkl"
    with open(fingerprint_path, 'rb') as f:
        fingerprint_db = pickle.load(f)
    
    metadata_path = "./database/tracks_metadata.json"
    with open(metadata_path, 'r', encoding='utf-8') as f:
        tracks_metadata = json.load(f)
    
    db_last_loaded = current_time
    return fingerprint_db, tracks_metadata

def visualize_match_distribution(match_counts, metadata, best_track_id=None, best_time_diff=None):
    os.makedirs("./match_plots", exist_ok=True)
    
    all_time_diffs = set()
    for track_id, time_diffs in match_counts.items():
        all_time_diffs.update(time_diffs.keys())
    
    time_diff_range = (min(all_time_diffs), max(all_time_diffs))
    print(f"Time offset range: {time_diff_range[0]} to {time_diff_range[1]}")
    
    for track_id, time_diffs in match_counts.items():
        if sum(time_diffs.values()) < 10:
            continue
            
        track_name = f"Unknown Track {track_id}"
        if str(track_id) in metadata:
            track_info = metadata[str(track_id)]
            track_name = f"{track_info['artist']} - {track_info['title']}"
        
        plt.figure(figsize=(12, 6))
        
        x_values = list(time_diffs.keys())
        y_values = list(time_diffs.values())
        
        plt.bar(x_values, y_values, width=3, alpha=0.7)
        
        if track_id == best_track_id and best_time_diff is not None:
            plt.axvline(x=best_time_diff, color='r', linestyle='--', 
                       label=f'Best Time Offset: {best_time_diff}')
            plt.legend()
        
        plt.xlabel('Time Offset (Query Time - DB Time)')
        plt.ylabel('Number of Matches')
        is_best = "(BEST MATCH)" if track_id == best_track_id else ""
        plt.title(f'Match Distribution for {track_name} {is_best}')
        
        buffer = (time_diff_range[1] - time_diff_range[0]) * 0.1
        plt.xlim(time_diff_range[0] - buffer, time_diff_range[1] + buffer)
        
        filename = f"./match_plots/track_{track_id}_histogram.png"
        plt.savefig(filename)
        plt.close()
        
        print(f"Saved histogram for Track {track_id} to {filename}")
    
    plt.figure(figsize=(14, 8))
    
    track_ids = []
    track_names = []
    peak_counts = []
    
    for track_id, time_diffs in match_counts.items():
        if not time_diffs:
            continue
            
        peak_count = max(time_diffs.values())
        
        if peak_count > 5:
            track_ids.append(track_id)
            
            if str(track_id) in metadata:
                track_info = metadata[str(track_id)]
                track_name = f"{track_info['artist']} - {track_info['title']}"
            else:
                track_name = f"Track {track_id}"
                
            track_names.append(track_name)
            peak_counts.append(peak_count)
    
    sorted_indices = sorted(range(len(peak_counts)), key=lambda i: peak_counts[i], reverse=True)
    track_names = [track_names[i] for i in sorted_indices]
    peak_counts = [peak_counts[i] for i in sorted_indices]
    track_ids = [track_ids[i] for i in sorted_indices]
    
    bars = plt.barh(track_names, peak_counts, alpha=0.7)
    
    if best_track_id is not None:
        for i, track_id in enumerate(track_ids):
            if track_id == best_track_id:
                bars[i].set_color('red')
                break
    
    plt.xlabel('Peak Match Count')
    plt.ylabel('Track')
    plt.title('Summary of Top Matching Tracks')
    plt.tight_layout()
    
    plt.savefig("./match_plots/summary_histogram.png")
    plt.close()
    
    print(f"Saved summary histogram to ./match_plots/summary_histogram.png")

def match_song(fingerprint_pairs):
    db, metadata = load_databases()
    
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
    
    # Visualize match distribution
    print("\nGenerating match distribution visualizations...")
    visualize_match_distribution(match_counts, metadata, best_track_id, best_time_diff)
    
    return track_metadata, confidence, best_time_diff

def main(fingerprint_pairs):
    track_metadata, confidence, time_diff = match_song(fingerprint_pairs)
    
    return {
        'track': track_metadata,
        'confidence': confidence,
        'time_offset': time_diff,
        'message': f"Best match: '{track_metadata['title']}' by {track_metadata['artist']}" if track_metadata else "No strong matches found"
    }

def test(audio_path="./songs_mp3/Novos Baianos - A Menina Dança.mp3", verbose=True):
    if verbose:
        print(f"Testing with audio file: {audio_path}")
    
    fingerprint = create_audio_fingerprint(audio_path)
    
    # Use the unified create_fingerprint_pairs function
    fingerprint_pairs, _ = create_fingerprint_pairs(fingerprint)
    
    if verbose:
        print("Matching against database...")
    
    result = main(fingerprint_pairs)
    
    if verbose:
        print("\nMatch result:")
        if result['track']:
            confidence_percent = result['confidence'] * 100
            confidence_level = "High" if confidence_percent > 70 else "Medium" if confidence_percent > 40 else "Low"
            
            print(f"Best match: '{result['track']['title']}' by {result['track']['artist']}")
            print(f"Confidence: {confidence_percent:.2f}% ({confidence_level})")
            print(f"Time offset: {result['time_offset']}")
        else:
            print("No strong matches found in database")
            print(f"Confidence: {result['confidence'] * 100:.2f}%")
    
    return result

if __name__ == "__main__":
    test("./songs_wav/Reptilia.wav")