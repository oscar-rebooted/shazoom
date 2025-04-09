import pdfplumber
import pandas as pd
import re

def extract_table_from_pdf(pdf_path):
    all_data = []
    extracted_ranks = set()  # Keep track of ranks we've already processed
    
    with pdfplumber.open(pdf_path) as pdf:
        # Skip first page (title page)
        for page_num in range(1, len(pdf.pages)):
            page = pdf.pages[page_num]
            print(f"\nProcessing page {page_num}...")
            
            # Track if this page yielded any valid rows
            page_data_extracted = False
            
            # Try multiple extraction methods
            extraction_methods = [
                # Method 1: Default table extraction
                lambda p: p.extract_tables(),
                
                # Method 2: Text-based table extraction (for shaded cells)
                lambda p: p.extract_tables({
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "explicit_vertical_lines": [],
                    "explicit_horizontal_lines": [],
                    "intersection_tolerance": 5
                }),
                
                # Method 3: Use text extraction + regex as last resort
                lambda p: extract_from_text(p)
            ]
            
            # Try each method until one works
            for method_idx, extraction_method in enumerate(extraction_methods):
                if page_data_extracted:
                    break
                    
                print(f"  Trying extraction method {method_idx + 1}...")
                
                try:
                    if method_idx < 2:  # Table extraction methods
                        tables = extraction_method(page)
                        valid_rows = process_tables(tables, all_data, extracted_ranks)
                        if valid_rows > 0:
                            page_data_extracted = True
                            print(f"  Method {method_idx + 1} extracted {valid_rows} rows")
                    else:  # Text extraction method
                        new_data = extraction_method(page)
                        if new_data:
                            # Filter out already extracted ranks
                            new_data = [item for item in new_data if item['Rank'] not in extracted_ranks]
                            if new_data:
                                all_data.extend(new_data)
                                extracted_ranks.update(item['Rank'] for item in new_data)
                                page_data_extracted = True
                                print(f"  Method {method_idx + 1} extracted {len(new_data)} rows")
                except Exception as e:
                    print(f"  Error with method {method_idx + 1}: {e}")
            
            if not page_data_extracted:
                print(f"  WARNING: No data could be extracted from page {page_num}")
    
    return all_data

def process_tables(tables, all_data, extracted_ranks):
    """Process extracted tables and return number of valid rows processed"""
    rows_processed = 0
    
    for table_idx, table in enumerate(tables):
        print(f"    Found table with {len(table)} rows")
        
        for row in table:
            # Skip rows without enough data
            if not row or len(row) < 3:
                continue
                
            # Ensure first cell is a digit (rank)
            if not row[0] or not str(row[0]).strip().isdigit():
                continue
                
            try:
                rank = int(str(row[0]).strip())
                
                # Skip if we've already processed this rank
                if rank in extracted_ranks:
                    continue
                    
                # Only accept ranks within expected range (1-1000)
                if rank < 1 or rank > 1000:
                    continue
                
                # Safely extract song, artist, and year with None checks
                song = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                artist = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
                
                # Only convert to int if it's a valid year
                year_str = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
                year = int(year_str) if year_str.isdigit() else None
                
                # Skip entries where song or artist is empty
                if not song or not artist:
                    continue
                
                all_data.append({
                    'Rank': rank,
                    'Song': song,
                    'Artist': artist,
                    'Year': year
                })
                extracted_ranks.add(rank)
                rows_processed += 1
            except (ValueError, IndexError, AttributeError) as e:
                print(f"    Error processing row: {row} - {e}")
                    
    return rows_processed

def extract_from_text(page):
    """Extract data using text extraction and regex as a last resort"""
    results = []
    text = page.extract_text()
    
    # Look for lines with the pattern: rank, song title, artist, year
    for line in text.split('\n'):
        # This regex looks for: number at start, text in middle, 4-digit year at end
        match = re.search(r'^\s*(\d+)\s+(.+?)\s+(\S+(?:\s+\S+){0,3})\s+(\d{4})\s*$', line)
        if match:
            try:
                rank = int(match.group(1))
                content = match.group(2).strip() + " " + match.group(3).strip()
                year = int(match.group(4))
                
                # Try to intelligently split content into song and artist
                # This is a heuristic and may need adjustment for your specific PDF
                words = content.split()
                if len(words) >= 4:
                    # Assume last 2 words are artist if 5+ words
                    # or last word is artist if 4 words
                    if len(words) >= 5:
                        song = " ".join(words[:-2])
                        artist = " ".join(words[-2:])
                    else:
                        song = " ".join(words[:-1])
                        artist = words[-1]
                else:
                    # For very short entries, just split in half
                    midpoint = len(words) // 2
                    song = " ".join(words[:midpoint])
                    artist = " ".join(words[midpoint:])
                
                results.append({
                    'Rank': rank,
                    'Song': song.strip(),
                    'Artist': artist.strip(),
                    'Year': year
                })
            except (ValueError, IndexError) as e:
                print(f"    Error processing line: {line[:50]}... - {e}")
    
    return results

def main():
    pdf_path = "The Top 1000 Songs of AllTime.pdf"
    
    # Extract data
    songs_data = extract_table_from_pdf(pdf_path)
    
    # Create DataFrame
    df = pd.DataFrame(songs_data)
    
    # Sort by rank to ensure order
    df = df.sort_values('Rank')
    
    # Check for missing ranks
    all_ranks = set(df['Rank'])
    missing_ranks = [i for i in range(1, 1001) if i not in all_ranks]
    if missing_ranks:
        print(f"\nWARNING: Missing {len(missing_ranks)} ranks:")
        print(f"Missing: {missing_ranks}")
    
    # Check if we have a good number of songs
    print(f"\nTotal songs extracted: {len(df)}")
    
    # Export to CSV
    csv_path = "top_1000_songs.csv"
    df.to_csv(csv_path, index=False)
    print(f"CSV file created: {csv_path}")

if __name__ == "__main__":
    main()