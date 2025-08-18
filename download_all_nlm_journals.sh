#!/bin/bash

# Download all papers from NLM journals using PubMed
# Organizes by: [broad_subject_term]/[title_full]/[year]
# Based on: data/nlm_journals/nlm_journals_consolidated.csv

set -e  # Exit on any error

# Configuration
CSV_FILE="data/nlm_journals/nlm_journals_consolidated.csv"
BASE_DIR="nlm_journals_data"
START_YEAR=1940
END_YEAR=2025
EMAIL="your-email@example.com"  # Replace with your email for NCBI
API_KEY=""  # Add your NCBI API key if you have one

echo "📚 NLM Journals PubMed Downloader"
echo "=================================="
echo "📄 Reading journals from: $CSV_FILE"
echo "📁 Output directory: $BASE_DIR"
echo "📅 Year range: $START_YEAR-$END_YEAR"
echo ""

# Create base directory
mkdir -p "$BASE_DIR"

# Function to sanitize directory names
sanitize_dirname() {
    echo "$1" | sed 's/[^a-zA-Z0-9 _-]/_/g' | sed 's/ /_/g' | sed 's/__*/_/g' | sed 's/_$//' | cut -c1-100
}

# Function to download papers for a journal in a specific year
download_journal_year() {
    local journal_name="$1"
    local output_file="$2"
    local year="$3"
    local temp_file="${output_file}.tmp"
    
    echo "    📄 Downloading $year..."
    
    # Build PubMed search query
    local query="\"$journal_name\"[Journal] AND (\"$year\"[Date - Publication] : \"$year\"[Date - Publication])"
    
    # Get article count first
    local count_result=$(esearch -db pubmed -query "$query" -email "$EMAIL" ${API_KEY:+-api_key "$API_KEY"} | efetch -format uid | wc -l | tr -d ' ')
    
    if [ "$count_result" -gt 0 ]; then
        # Download to temporary file
        if esearch -db pubmed -query "$query" -email "$EMAIL" ${API_KEY:+-api_key "$API_KEY"} | efetch -format medline > "$temp_file" 2>/dev/null; then
            # Check if temporary file has content
            if [ -s "$temp_file" ]; then
                mv "$temp_file" "$output_file"
                echo "    ✅ Downloaded $count_result articles for $year"
                return 0
            else
                rm -f "$temp_file"
                echo "    ⚠️  Empty download for $year"
                return 1
            fi
        else
            rm -f "$temp_file"
            echo "    ❌ Download failed for $year"
            return 1
        fi
    else
        echo "    ⚠️  No articles found for $year"
        return 1
    fi
}

# Read CSV and process each journal
total_journals=0
processed_journals=0

echo "🔍 Processing NLM journals..."

# Skip header line and process each journal
tail -n +2 "$CSV_FILE" | while IFS=',' read -r broad_subject_term entry_number title_abbreviation title_full rest; do
    total_journals=$((total_journals + 1))
    
    # Skip if no title_full
    if [ -z "$title_full" ] || [ "$title_full" = '""' ]; then
        echo "⏭️  Skipping journal $entry_number (no full title)"
        continue
    fi
    
    # Clean up CSV field values (remove quotes)
    broad_subject_term=$(echo "$broad_subject_term" | sed 's/^"//; s/"$//')
    title_full=$(echo "$title_full" | sed 's/^"//; s/"$//')
    
    # Sanitize directory names
    safe_subject=$(sanitize_dirname "$broad_subject_term")
    safe_title=$(sanitize_dirname "$title_full")
    
    echo ""
    echo "📖 Processing Journal #$entry_number"
    echo "   📂 Subject: $broad_subject_term"
    echo "   📄 Title: $title_full"
    echo "   📁 Directory: $safe_subject/$safe_title"
    
    # Create directory structure
    journal_dir="$BASE_DIR/$safe_subject/$safe_title"
    mkdir -p "$journal_dir"
    
    # Create medline subdirectory
    medline_dir="$journal_dir/medline"
    mkdir -p "$medline_dir"
    
    # Download papers for each year
    downloaded_years=0
    for year in $(seq $START_YEAR $END_YEAR); do
        output_file="$medline_dir/${safe_title}_${year}.txt"
        
        # Skip if file already exists
        if [ -f "$output_file" ]; then
            echo "    ⏭️  Skipping $year (file exists)"
            continue
        fi
        
        if download_journal_year "$title_full" "$output_file" "$year"; then
            downloaded_years=$((downloaded_years + 1))
        fi
        
        # Rate limiting - be nice to NCBI
        sleep 0.5
    done
    
    if [ $downloaded_years -gt 0 ]; then
        processed_journals=$((processed_journals + 1))
        echo "   ✅ Journal completed: $downloaded_years years downloaded"
        
        # Create summary file
        echo "Journal: $title_full" > "$journal_dir/journal_info.txt"
        echo "Subject: $broad_subject_term" >> "$journal_dir/journal_info.txt"
        echo "Entry Number: $entry_number" >> "$journal_dir/journal_info.txt"
        echo "Downloaded Years: $downloaded_years" >> "$journal_dir/journal_info.txt"
        echo "Downloaded Date: $(date)" >> "$journal_dir/journal_info.txt"
    else
        echo "   ⚠️  No papers downloaded for this journal"
        # Remove empty directory
        rmdir "$medline_dir" 2>/dev/null || true
        rmdir "$journal_dir" 2>/dev/null || true
    fi
    
    # Progress update every 10 journals
    if [ $((total_journals % 10)) -eq 0 ]; then
        echo ""
        echo "📊 Progress: $processed_journals journals with data / $total_journals total processed"
        echo ""
    fi
done

echo ""
echo "🎉 NLM Journals Download Complete!"
echo "📊 Final Summary:"
echo "   📚 Total journals processed: $total_journals"
echo "   ✅ Journals with downloaded papers: $processed_journals"
echo "   📁 Data location: $BASE_DIR/"
echo ""
echo "💡 Next step: Run parse_nlm_journals_to_json.py to convert MEDLINE to JSON"
