#!/bin/bash

# Script to download oral health articles from PubMed using Entrez
# Downloads articles from 1940 to 2025, one file per year
# Uses oral health MeSH terms: Stomatognathic Diseases, Dentistry, Oral Health

# Create the output directory if it doesn't exist
mkdir -p data/pubmed_entrez_search

# Check if EDirect tools are available
if ! command -v esearch &> /dev/null; then
    echo "Error: EDirect tools (esearch/efetch) are not installed or not in PATH"
    echo "Please install EDirect tools from NCBI first"
    echo "Installation: https://www.ncbi.nlm.nih.gov/books/NBK179288/"
    exit 1
fi

echo "Starting PubMed download for oral health articles (1940-2025)..."
echo "🦷 Using MeSH terms: Stomatognathic Diseases, Dentistry, Oral Health"

# Loop through years 1940 to 2025
for year in {1940..2025}
do
    echo "Downloading articles for year: $year"
    
    # Create the query with the current year using oral health MeSH terms
    # For older articles (pre-1966), use broader MeSH Terms; for newer articles use Major Topic
    # Note: MeSH indexing started in 1966, so use more flexible terms for earlier years
    if [ "$year" -lt 1966 ]; then
        # For pre-1966 articles, use broader search with title/abstract and general MeSH terms
        query="((Stomatognathic Diseases[MeSH Terms]) OR (Dentistry[MeSH Terms]) OR (Oral Health[MeSH Terms]) OR (dentistry[Title/Abstract]) OR (dental[Title/Abstract]) OR (oral health[Title/Abstract]) OR (stomatology[Title/Abstract])) AND (\"${year}\"[Date - Publication] : \"${year}\"[Date - Publication])"
    else
        # For 1966+ articles, use MeSH Major Topic for more precision
        query="(((Stomatognathic Diseases[MeSH Major Topic]) OR (Dentistry[MeSH Major Topic]) OR (Oral Health[MeSH Major Topic])) AND (\"${year}\"[Date - Publication] : \"${year}\"[Date - Publication]))"
    fi
    
    # Output file name
    output_file="data/pubmed_entrez_search/oralevidencedb_pubmed_${year}.txt"
    
    # Run the esearch and efetch commands
    esearch -db pubmed -query "$query" | efetch -format medline > "$output_file"
    
    # Check if the command was successful
    if [ $? -eq 0 ]; then
        # Get the file size to verify content was downloaded
        file_size=$(wc -c < "$output_file" 2>/dev/null || echo "0")
        if [ "$file_size" -gt 0 ]; then
            echo "✓ Successfully downloaded articles for $year (${file_size} bytes)"
        else
            echo "⚠ Warning: No articles found for year $year (empty file)"
        fi
    else
        echo "✗ Error downloading articles for year $year"
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
