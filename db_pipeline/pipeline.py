#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

import requests
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configuration
YT_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL_oFlvgqkrjUVQwiiE3F3k3voF4tjXeP0"
DOWNLOAD_DIR = "downloads/webm"
MP3_DIR = "downloads/mp3"
METADATA1_PATH = "metadata_youtube.json"
METADATA2_PATH = "metadata_spotify.json"
SPOTIFY_RATE_LIMIT = 100  # requests per minute
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

class YouTubeDownloader:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
    def download_playlist(self, playlist_url: str, start_idx: int = 1, end_idx: int = 5) -> List[str]:
        """Download audio from YouTube playlist and return downloaded filenames"""
        # Create command with your preferred options
        cmd = [
            "yt-dlp",
            "--limit-rate", "1M",
            # "--sleep-interval", "3",
            # "--max-sleep-interval", "7",
            "-f", "ba",
            "--print", "after_move:filepath",  # Add this to print actual file paths            
            "-o", f"{self.download_dir}/%(title)s [%(id)s].%(ext)s",  # Explicitly set output path
            "--playlist-items", f"{start_idx}-{end_idx}",
            "--max-filesize", "20M",
            # "--match-filter", "language=en",  # Only download songs in English
            playlist_url
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        
        # Execute the command and capture output
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error downloading videos: {result.stderr}")
            return []
        
        # Parse filenames from output
        filenames = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        print(f"Downloaded {len(filenames)} files")
        
        # Verify files exist
        existing_files = [f for f in filenames if os.path.exists(f)]
        if len(existing_files) != len(filenames):
            print(f"Warning: Only {len(existing_files)} of {len(filenames)} reported files actually exist")
            
        return existing_files

class AudioConverter:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def convert_to_mp3(self, input_files: List[str]) -> List[str]:
        """Convert audio files to MP3 format and return the new file paths"""
        mp3_files = []
        
        for input_file in tqdm(input_files, desc="Converting to MP3"):
            # Create output path with mp3 extension
            filename = os.path.basename(input_file)
            name_without_ext = os.path.splitext(filename)[0]
            output_file = os.path.join(self.output_dir, f"{name_without_ext}.mp3")
            
            # Convert using ffmpeg
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file if it exists
                "-i", input_file,
                "-vn",  # No video
                "-ar", "44100",  # Audio sampling rate
                "-ac", "2",  # Audio channels
                "-b:a", "192k",  # Audio bitrate
                output_file
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                mp3_files.append(output_file)
                print(f"Converted: {output_file}")
            except subprocess.CalledProcessError as e:
                print(f"Error converting {input_file}: {e.stderr.decode()}")
        
        return mp3_files

class MetadataProcessor:
    def __init__(self, metadata_path: str):
        self.metadata_path = metadata_path
        # Initialize or load existing metadata
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def extract_title(self, filename: str) -> str:
        """Clean the YouTube filename to extract just the title"""
        # Remove the path and extension
        basename = os.path.basename(filename)
        name_without_ext = os.path.splitext(basename)[0]
        
        # Remove YouTube ID in square brackets
        clean_title = re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]\s*$', '', name_without_ext)
        
        return clean_title
    
    def clean_youtube_title(self, title: str) -> str:
        """Clean the YouTube title by removing expressions but keeping feat/ft"""
        # Remove various official video/music video markers
        pattern = r'[\(\[](?:Official(?:\s+(?:Music|Lyric|HD))?(?:\s+Video)?|MV|M/V|Live|Ao Vivo|LETRA|Lyrics|Video Oficial)[\)\]]\s*'
        cleaned_title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        return cleaned_title.strip()
    
    def extract_artist_and_title(self, youtube_title: str) -> Tuple[str, str]:
        """Extract artist and title from the YouTube title"""
        youtube_title_cleaned = self.clean_youtube_title(youtube_title)
        
        # Handle the case: "artist - title ft. featuring_artists"
        if " - " in youtube_title_cleaned:
            parts = youtube_title_cleaned.split(" - ", 1)
            artist = parts[0].strip()
            title_part = parts[1].strip()
            
            # Extract title without featuring artists
            if " ft." in title_part.lower():
                title = title_part.split(" ft.", 1)[0].strip()
            elif " feat." in title_part.lower():
                title = title_part.split(" feat.", 1)[0].strip()
            else:
                title = title_part
                
        # Handle the case: "artist ft. featuring_artists - title"
        elif "ft. " in youtube_title_cleaned.lower() and " - " in youtube_title_cleaned.split("ft. ", 1)[1]:
            artist_part = youtube_title_cleaned.split(" - ", 1)[0].strip()
            title = youtube_title_cleaned.split(" - ", 1)[1].strip()
            
            # Extract main artist without featuring artists
            if " ft." in artist_part.lower():
                artist = artist_part.split(" ft.", 1)[0].strip()
            elif " feat." in artist_part.lower():
                artist = artist_part.split(" feat.", 1)[0].strip()
            else:
                artist = artist_part
        
        # Default case if pattern doesn't match
        else:
            artist = ""
            title = youtube_title_cleaned
            
        return artist, title
    
    def add_entry(self, shazoom_id: str, filename: str) -> None:
        """Add a new entry to the metadata"""
        # Get basename without extension
        basename = os.path.basename(filename)
        # name_without_ext = os.path.splitext(basename)[0]
        
        # Extract original YouTube title
        youtube_title_v1 = self.extract_title(filename)
        
        # Clean the title (remove official tags)
        youtube_title_v2 = self.clean_youtube_title(youtube_title_v1)
        
        # Extract artist and title_v3
        artist, youtube_title_v3 = self.extract_artist_and_title(youtube_title_v1)
        
        self.metadata[shazoom_id] = {
            "original_filename": basename,
            "youtube": {
                "youtube_title_v1": youtube_title_v1,
                "youtube_title_v2": youtube_title_v2,
                "youtube_title_v3": youtube_title_v3,
                "youtube_artist": artist
            }
        }
    
    def save(self) -> None:
        """Save metadata to disk"""
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        print(f"Saved metadata to {self.metadata_path}")

class SpotifyEnricher:
    def __init__(self, client_id: str, client_secret: str, rate_limit: int):
        if not client_id or not client_secret:
            raise ValueError("Spotify client ID and client secret must be provided")
        self.client_id = client_id
        self.client_secret = client_secret
        self.rate_limit = rate_limit
        self.token = None
        self.token_expiry = 0
        self.request_count = 0
        self.last_request_time = 0
    
    def get_token(self) -> str:
        """Get or refresh Spotify API token"""
        current_time = time.time()
        if not self.token or current_time >= self.token_expiry:
            auth_response = requests.post('https://accounts.spotify.com/api/token', {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            })
            auth_response.raise_for_status()
            auth_data = auth_response.json()
            self.token = auth_response.json()['access_token']
            self.token_expiry = current_time + auth_data['expires_in'] - 60  # Buffer of 60 seconds
        return self.token
    
    def respect_rate_limit(self) -> None:
        """Ensure we don't exceed Spotify's rate limit"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # Reset counter if a minute has passed
        if elapsed > 60:
            self.request_count = 0
            self.last_request_time = current_time
        
        # If we're approaching the rate limit, sleep
        if self.request_count >= self.rate_limit:
            sleep_time = 60 - elapsed + 1  # Add 1 second buffer
            if sleep_time > 0:
                print(f"Rate limit approaching. Sleeping for {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
                self.request_count = 0
                self.last_request_time = time.time()
    
    def search_track(self, title: str, artist: str) -> Optional[Dict]:
        """Search for a track on Spotify by title and artist"""
        self.respect_rate_limit()
        
        token = self.get_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        # Construct query with track and artist parameters
        query = f"track:{title} artist:{artist}"
        params = {'q': query, 'type': 'track', 'limit': 1}
        
        response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
        self.request_count += 1
        self.last_request_time = time.time()
        
        if response.status_code != 200:
            print(f"Error searching for '{title}' by '{artist}': {response.status_code}")
            return None
        
        data = response.json()
        tracks = data.get('tracks', {}).get('items', [])
        
        if not tracks:
            print(f"No tracks found for '{title}' by '{artist}'")
            return None
        
        track = tracks[0]
        return {
            "title": track["name"],  # Spotify's title for the track
            "artist": ", ".join(artist["name"] for artist in track["artists"]),
            "album": track["album"]["name"],
            "year": int(track["album"]["release_date"][:4]) if track["album"]["release_date"] else None,
            "albumCover": track["album"]["images"][0]["url"] if track["album"]["images"] else None
        }
    
    def enrich_metadata(self, basic_metadata: Dict, output_path: str, processed_ids: Optional[List[str]] = None) -> List[str]:
        """Enrich basic metadata with Spotify data, only for new entries not already processed"""
        # Load existing enriched metadata if it exists
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                enriched_metadata = json.load(f)
        else:
            enriched_metadata = {}
        
        # Determine which records need to be processed
        if processed_ids is None:
            processed_ids = list(enriched_metadata.keys())
        
        # Only process new entries that haven't been processed yet
        new_ids = [shazoom_id for shazoom_id in basic_metadata.keys() 
                   if shazoom_id not in processed_ids]
        
        if not new_ids:
            print("No new tracks to enrich with Spotify data")
            return processed_ids
        
        print(f"Enriching metadata for {len(new_ids)} new tracks")
        for shazoom_id in tqdm(new_ids):
            entry = basic_metadata[shazoom_id]
            title = entry["youtube"]["youtube_title_v3"]
            artist = entry["youtube"]["youtube_artist"]
            
            # Get additional metadata from Spotify using both title and artist
            spotify_data = self.search_track(title, artist)
                        
            entry["spotify"] = {}
            # Add other Spotify data if available
            if spotify_data:
                for key, value in spotify_data.items():
                    entry["spotify"][key] = value
            
            enriched_metadata[shazoom_id] = entry
            processed_ids.append(shazoom_id)
        
        # Save enriched metadata
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_metadata, f, indent=2, ensure_ascii=False)
        
        print(f"Saved enriched metadata to {output_path}")
        return processed_ids

def main():
    # Check for Spotify credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("Please set your Spotify API credentials in environment variables")
        return
    
    # Initialize components
    downloader = YouTubeDownloader(DOWNLOAD_DIR)
    converter = AudioConverter(DOWNLOAD_DIR, MP3_DIR)
    metadata_proc = MetadataProcessor(METADATA1_PATH)
    spotify = SpotifyEnricher(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_RATE_LIMIT)
    
    # Keep track of which IDs have been processed for Spotify enrichment
    processed_spotify_ids = []
    
    id_counter = 0
    # Download videos (adjust range as needed for your 1000 songs)
    # Split into smaller batches to avoid overwhelming your system
    batch_size = 2
    total_videos = 50
    
    for start_idx in range(1, total_videos, batch_size):
        end_idx = min(start_idx + batch_size - 1, total_videos)
        print(f"Downloading videos {start_idx} to {end_idx}...")
        
        # Step 1: Download webm files
        webm_files = downloader.download_playlist(
            YT_PLAYLIST_URL, 
            start_idx=start_idx, 
            end_idx=end_idx
        )
        
        # Step 2: Convert webm to mp3
        mp3_files = converter.convert_to_mp3(webm_files)

        # Step 3: Process each converted mp3 file        
        for filename in mp3_files:
            # Create shazoom_id using deterministic hash which outputs integers only
            # base_filename = os.path.basename(filename)
            # hash_obj = hashlib.sha256(base_filename.encode('utf-8'))
            # hash_digest = hash_obj.digest()
            # shazoom_id = int.from_bytes(hash_digest[:8], byteorder='big') 
            # shazoom_id = shazoom_id & 0x7FFFFFFFFFFFFFFF            
            
            shazoom_id = id_counter & 0xFFFF  # Mask to 16 bits, as 2**16 = 65,535
            id_counter +=1 

            # Add to basic metadata
            metadata_proc.add_entry(shazoom_id, filename)
        
        # Save progress after each batch
        metadata_proc.save()
        
        # Enrich only this new batch with Spotify data
        processed_spotify_ids = spotify.enrich_metadata(
            metadata_proc.metadata, 
            METADATA2_PATH,
            processed_spotify_ids
        )
        print(f"Enriched batch {start_idx}-{end_idx} with Spotify data")
    
    print("Pipeline complete!")

if __name__ == "__main__":
    main()