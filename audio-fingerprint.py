import numpy as np
import librosa
import scipy.ndimage

def create_audio_fingerprint(audio_path, target_peaks_per_second=30, window_length=1024, hop_length=32, num_bands=6):
    y, sr = librosa.load(audio_path, mono=True, sr=8192)
    
    D = librosa.stft(y, n_fft=window_length, hop_length=hop_length)
    
    magnitude = np.abs(D)
    
    freq_bins = magnitude.shape[0]
    bands = []
    
    band_edges = np.logspace(np.log10(1), np.log10(freq_bins-1), num_bands + 1).astype(int)
    band_edges[0] = 0
    
    for i in range(num_bands):
        start = band_edges[i]
        end = band_edges[i + 1]
        bands.append((start, end))
    
    band_peaks = np.zeros_like(magnitude)
    
    for t in range(magnitude.shape[1]):
        for start, end in bands:
            band_magnitude = magnitude[start:end, t]
            
            if len(band_magnitude) > 0:
                max_idx = np.argmax(band_magnitude) + start
                band_peaks[max_idx, t] = magnitude[max_idx, t]
    
    neighbourhood_size = 30
    
    max_filtered = scipy.ndimage.maximum_filter(band_peaks, size=(neighbourhood_size, neighbourhood_size))
    peak_mask = (band_peaks == max_filtered) & (band_peaks > 0)
    
    peak_coordinates = np.argwhere(peak_mask)
    
    fingerprint = [(time, freq) for freq, time in peak_coordinates]
    
    print(f"Number of peaks found: {len(fingerprint)}")
    
    return fingerprint

def create_fingerprint_pairs(fingerprint, target_zone_frames=50):
    pairs = []
    
    sorted_peaks = sorted(fingerprint, key=lambda x: x[0])
    
    for i, anchor_point in enumerate(sorted_peaks):
        anchor_time, anchor_freq = anchor_point
        
        for j in range(i+1, len(sorted_peaks)):
            target_point = sorted_peaks[j]
            target_time, target_freq = target_point
            
            time_diff = target_time - anchor_time
            if time_diff > target_zone_frames:
                break
                
            # Always include the anchor time for matching
            pair = (anchor_freq, target_freq, time_diff, anchor_time)
            pairs.append(pair)
    
    print(f"Generated {len(pairs)} fingerprint pairs")
    
    return pairs, sorted_peaks

def hash_function(freq1, freq2, delta_t):
    return (freq1 << 20) | (freq2 << 10) | delta_t

def quantize_value(value, bin_size):
    return (value // bin_size) * bin_size

def get_nearby_hashes(freq1, freq2, delta_t, freq_bin=2, time_bin=2):
    q_freq1 = quantize_value(freq1, freq_bin)
    q_freq2 = quantize_value(freq2, freq_bin)
    q_delta_t = quantize_value(delta_t, time_bin)
    
    primary_hash = hash_function(q_freq1, q_freq2, q_delta_t)
    
    hashes = [primary_hash]
    
    variations = [
        (q_freq1 + freq_bin, q_freq2, q_delta_t),
        (q_freq1 - freq_bin, q_freq2, q_delta_t),
        (q_freq1, q_freq2 + freq_bin, q_delta_t),
        (q_freq1, q_freq2 - freq_bin, q_delta_t),
        (q_freq1, q_freq2, q_delta_t + time_bin),
        (q_freq1, q_freq2, q_delta_t - time_bin)
    ]
    
    for f1, f2, dt in variations:
        if 0 <= f1 < 1024 and 0 <= f2 < 1024 and 0 <= dt < 1024:
            hashes.append(hash_function(f1, f2, dt))
    
    return hashes