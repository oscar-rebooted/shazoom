# test commit

import numpy as np
import librosa
import scipy.signal
import matplotlib.pyplot as plt

def create_audio_fingerprint(audio_path):
    """
    Create an audio fingerprint using the Shazam-like algorithm
    as described in the Wang 2003 paper and implemented in 
    Khatri, Dillingham & Chen 2019
    
    Parameters:
    -----------
    audio_path : str
        Path to the audio file
    
    Returns:
    --------
    fingerprint : list of tuples
        List of (time, frequency) peaks representing the audio fingerprint
    """
    # 1. Load and preprocess the audio
    # Convert to mono (averages the stereo channels) and downsample
    # 8192 Hz is chosen because most relevant audio information is below 4096 Hz
    y, sr = librosa.load(audio_path, mono=True, sr=8192)
    
    # 2. Compute Short-Time Fourier Transform (STFT)
    # Use parameters from the paper:
    # - Window length: 1024
    # - Hop size: 32 (smaller hop size compensates for different start times)
    window_length = 1024
    hop_length = 32
    
    # Compute spectrogram
    # Note: librosa.stft uses a Hann window by default, which is fine for our purposes
    D = librosa.stft(y, n_fft=window_length, hop_length=hop_length)
    
    # 3. Compute energy spectrogram (ignoring phase information)
    # Using energy (squared magnitude) instead of just magnitude can emphasize stronger frequency components
    energy = np.abs(D)**2
    
    # 4. Divide frequency bins into logarithmic bands
    num_bands = 6
    
    # Create logarithmic frequency bands
    # The frequency bins go from 0 to Nyquist (4096 Hz)
    # Using logarithmic bands to better match human hearing
    freq_bins = magnitude.shape[0]  # 513 bins
    bands = []
    
    # Create logarithmic band divisions
    # Using exponential spacing to create logarithmic bands
    # Start with 1 instead of 0 to avoid log(0) which is undefined
    band_edges = np.logspace(np.log10(1), np.log10(freq_bins-1), num_bands + 1).astype(int)
    band_edges[0] = 0  # Manually set first edge to 0
    
    for i in range(num_bands):
        start = band_edges[i]
        end = band_edges[i + 1]
        bands.append((start, end))
    
    # 5. For each time frame and each frequency band, find the maximum
    band_peaks = np.zeros_like(energy)
    
    for t in range(energy.shape[1]):
        for start, end in bands:
            # Extract the energy for this band
            band_energy = energy[start:end, t]
            
            # Find index of max in this band
            if len(band_energy) > 0:
                max_idx = np.argmax(band_energy) + start
                # Set only the max value to its original value, zero out others
                band_peaks[max_idx, t] = energy[max_idx, t]
    
    # 6. Apply max filter to identify local peaks
    # The max filter makes neighbourhoods of pixels have the max value in that neighbourhood
    neighbourhood_size = 300  # 300x300 neighbourhood for local maxima
    max_filtered = scipy.ndimage.maximum_filter(band_peaks, size=(neighbourhood_size, neighbourhood_size))
    
    # 7. Find local maxima by comparing original to max filtered version
    # Only points that are the max in their neighborhood will be the same in both
    peak_mask = (band_peaks == max_filtered) & (band_peaks > 0)
    
    # 8. Get the coordinates of all peak points
    peak_coordinates = np.argwhere(peak_mask)
    
    # Convert to list of (time, frequency) tuples for the fingerprint
    fingerprint = [(time, freq) for freq, time in peak_coordinates]
    
    return fingerprint

def plot_fingerprint(audio_path):
    """
    Create and visualize the fingerprint constellation
    """
    # Get the fingerprint
    fingerprint = create_audio_fingerprint(audio_path)
    
    # Load audio for visualization
    y, sr = librosa.load(audio_path, mono=True, sr=8192)
    
    # Compute spectrogram for visualization
    D = librosa.stft(y, n_fft=1024, hop_length=32)
    energy = np.abs(D)**2
    energy_db = librosa.power_to_db(energy, ref=np.max)
    
    # Plot spectrogram
    plt.figure(figsize=(12, 6))
    librosa.display.specshow(energy_db, sr=sr, hop_length=32, x_axis='time', y_axis='hz')
    plt.xticks(np.arange(0, len(y)/sr, 30))
    plt.colorbar(format='%+2.0f dB')
    
    # Plot the fingerprint points on top
    time_points = [f[0] for f in fingerprint]
    freq_points = [f[1] for f in fingerprint]
    plt.scatter(time_points, freq_points, color='red', s=1, alpha=0.7)
    
    plt.title('Audio Fingerprint Constellation')
    plt.tight_layout()
    plt.show()

def create_fingerprint_pairs(fingerprint, target_zone_frames=50):
    """
    Create pairs from fingerprint peaks
    
    Parameters:
    -----------
    fingerprint : list of tuples
        List of (time, frequency) peaks
    target_zone_frames : int
        Number of frames to the right of anchor point to consider
    
    Returns:
    --------
    pairs : list of tuples
        List of (freq_1, freq_2, delta_t) pairs
    """
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
            
            # Check if the target point is within the target zone (50 frames to the right)
            time_diff = target_time - anchor_time
            if time_diff > target_zone_frames:
                break  # We've gone beyond the target zone
                
            # Create pair
            pair = (anchor_freq, target_freq, time_diff)
            pairs.append(pair)
    
    return pairs

# Example usage
if __name__ == '__main__':
    # Example audio file path
    audio_path = 'path/to/your/audio/file.mp3'
    
    # Generate fingerprint
    fingerprint = create_audio_fingerprint(audio_path)
    
    # Create fingerprint pairs
    pairs = create_fingerprint_pairs(fingerprint)
    
    # Print some information about the fingerprint
    print(f"Number of peaks in constellation: {len(fingerprint)}")
    print(f"Number of fingerprint pairs: {len(pairs)}")
    
    # Optional: Visualize the fingerprint
    # plot_fingerprint(audio_path)