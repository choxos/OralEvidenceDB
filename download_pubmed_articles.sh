#!/bin/bash

# Script to download oral health articles from PubMed using Entrez
# Downloads articles from specified year range (default: 1940 to 2025)
# Uses oral health MeSH terms: Stomatognathic Diseases, Dentistry, Oral Health

# Default year range
START_YEAR=1940
END_YEAR=2025

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--start)
            START_YEAR="$2"
            shift 2
            ;;
        -e|--end)
            END_YEAR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -s, --start YEAR    Start year (default: 1940)"
            echo "  -e, --end YEAR      End year (default: 2025)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Download 1940-2025"
            echo "  $0 -s 2020 -e 2025  # Download 2020-2025"
            echo "  $0 -s 2025 -e 2025  # Download only 2025"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Validate year range
if ! [[ "$START_YEAR" =~ ^[0-9]+$ ]] || ! [[ "$END_YEAR" =~ ^[0-9]+$ ]]; then
    echo "Error: Start and end years must be numbers"
    exit 1
fi

if [ "$START_YEAR" -gt "$END_YEAR" ]; then
    echo "Error: Start year cannot be greater than end year"
    exit 1
fi

echo "Downloading articles for years $START_YEAR to $END_YEAR"

# Create the output directory if it doesn't exist
mkdir -p data/pubmed_entrez_search

# Check if EDirect tools are available
if ! command -v esearch &> /dev/null; then
    echo "Error: EDirect tools (esearch/efetch) are not installed or not in PATH"
    echo "Please install EDirect tools from NCBI first"
    echo "Installation: https://www.ncbi.nlm.nih.gov/books/NBK179288/"
    exit 1
fi

echo "Starting PubMed download for oral health articles ($START_YEAR-$END_YEAR)..."
echo "🦷 Using MeSH terms: Stomatognathic Diseases, Dentistry, Oral Health"

# Loop through the specified year range
for year in $(seq $START_YEAR $END_YEAR)
do
    echo "Downloading articles for year: $year"
    
    # Create the query with the current year using oral health MeSH terms
    # Note: Using MeSH Major Topic for precision and consistency
    query="(((Stomatognathic Diseases[MeSH Major Topic]) OR (Dentistry[MeSH Major Topic]) OR (Oral Health[MeSH Major Topic])) AND (\"${year}\"[Date - Publication] : \"${year}\"[Date - Publication]))"
    
    # Output file name
    output_file="data/pubmed_entrez_search/oralevidencedb_pubmed_${year}.txt"
    
    # First check if there are any articles for this year
    article_count=$(esearch -db pubmed -query "$query" | efetch -format uid | wc -l | tr -d ' ')
    
    if [ "$article_count" -gt 0 ]; then
        # There are articles, so download them to a temporary file first
        temp_file="${output_file}.tmp"
        esearch -db pubmed -query "$query" | efetch -format medline > "$temp_file"
        
        # Check if the download was successful and has content
        if [ $? -eq 0 ] && [ -s "$temp_file" ]; then
            # File has content, move it to final location
            mv "$temp_file" "$output_file"
            file_size=$(wc -c < "$output_file" 2>/dev/null || echo "0")
            echo "✓ Successfully downloaded articles for $year (${article_count} articles, ${file_size} bytes)"
        else
            # Download failed or file is empty, remove temp file
            rm -f "$temp_file"
            echo "⚠ No content downloaded for year $year (no file created)"
        fi
    else
        echo "⊝ No articles found for year $year (no file created)"
    fi
    
    # Add a small delay to be respectful to NCBI servers
    sleep 1
done

echo ""
echo "🎉 Download completed!"
echo "Files saved in: $(pwd)/data/pubmed_entrez_search/"

# Display summary
echo ""
echo "📊 Summary:"
total_files=$(ls data/pubmed_entrez_search/oralevidencedb_pubmed_*.txt 2>/dev/null | wc -l)
non_empty_files=$(find data/pubmed_entrez_search -name "oralevidencedb_pubmed_*.txt" -size +0c 2>/dev/null | wc -l)
echo "Total files created: $total_files"
echo "Non-empty files: $non_empty_files"

if [ "$non_empty_files" -gt 0 ]; then
    echo ""
    echo "📈 Largest files:"
    find data/pubmed_entrez_search -name "oralevidencedb_pubmed_*.txt" -size +0c -exec ls -lh {} \; | sort -k5 -hr | head -5
fi

echo ""
echo "🔄 Next steps:"
echo "1. Run parsing script: python scripts/parse_medline_to_json_by_year.py"
echo "2. Import to database: python import_all_years_corrected.py"
echo "3. Monitor import progress in Django admin panel"
