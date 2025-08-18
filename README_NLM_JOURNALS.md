# NLM Journals PubMed Downloader

🦷 **Download all papers from every journal in the NLM catalog, organized by subject and year**

This toolkit downloads papers from all ~16,000 journals in the NLM (National Library of Medicine) catalog and organizes them exactly as requested:

```
[broad_subject_term]/[title_full]/[year]/[pmid].json
```

## 📁 Output Structure

```
nlm_journals_data/
├── Dentistry/
│   ├── Journal_of_Dental_Research/
│   │   ├── medline/                    # Raw MEDLINE files
│   │   │   ├── Journal_of_Dental_Research_2023.txt
│   │   │   ├── Journal_of_Dental_Research_2022.txt
│   │   │   └── ...
│   │   ├── json/                       # Parsed JSON files  
│   │   │   ├── 2023/
│   │   │   │   ├── 36789123.json      # Individual papers
│   │   │   │   ├── 36789124.json
│   │   │   │   └── ...
│   │   │   ├── 2022/
│   │   │   └── ...
│   │   ├── journal_info.txt            # Journal metadata
│   │   └── parsing_summary.json       # Processing statistics
│   ├── Oral_Surgery_Oral_Medicine/
│   └── ...
├── Cardiology/
│   ├── Circulation/
│   └── ...
└── ...
```

## 🚀 Quick Start

### Prerequisites

1. **NCBI E-utilities** (required for PubMed access):
   ```bash
   # Using conda (recommended)
   conda install -c bioconda entrez-direct
   
   # Or using apt (Ubuntu/Debian)
   sudo apt-get install ncbi-entrez-direct
   
   # Or using homebrew (macOS)
   brew install ncbi-entrez-direct
   ```

2. **Python 3.7+** with standard libraries

3. **NCBI Email** (required for API access)

### Simple Usage

```bash
# Download and parse everything (WARNING: ~7-10 days, 50-100 GB)
python run_nlm_journals_download.py --email your@email.com

# Focus on specific subject area (much faster)
python run_nlm_journals_download.py --email your@email.com --subject "Dentistry"

# Show time/storage estimates first
python run_nlm_journals_download.py --estimate
```

### Advanced Usage

```bash
# Download only (skip JSON parsing)
python run_nlm_journals_download.py --email your@email.com --download-only

# Parse existing downloads only (skip downloading)
python run_nlm_journals_download.py --parse-only

# Use NCBI API key for faster downloads (optional)
python run_nlm_journals_download.py --email your@email.com --api-key YOUR_API_KEY

# Resume interrupted downloads
./download_all_nlm_journals.sh  # Will skip existing files automatically

# Parse specific subject only
python parse_nlm_journals_to_json.py --subject "Dentistry"
```

## 📊 Scale & Performance

| Metric | Estimate |
|--------|----------|
| **Total Journals** | ~16,000 journals |
| **Year Range** | 1940-2025 (85 years) |
| **Total Queries** | ~1.3 million PubMed queries |
| **Download Time** | 7-10 days continuous |
| **Storage Required** | 50-100 GB |
| **Rate Limit** | ~2 queries/second (NCBI limit) |

### Subject Areas Include:
- Dentistry (~200 journals)
- Cardiology (~300 journals)  
- Neurology (~400 journals)
- Oncology (~500 journals)
- And 100+ other medical specialties

## 🛠️ Individual Scripts

### 1. Download Script
```bash
./download_all_nlm_journals.sh
```
- Downloads raw MEDLINE files from PubMed
- Organizes by subject/journal/year
- Automatically resumes interrupted downloads
- Respects NCBI rate limits

### 2. Parsing Script
```bash
python parse_nlm_journals_to_json.py [options]
```

Options:
- `--data-dir`: Base directory (default: `nlm_journals_data`)
- `--subject`: Process specific subject only
- `--journal`: Process specific journal only  
- `--resume`: Skip already processed journals

### 3. Master Script
```bash
python run_nlm_journals_download.py [options]
```

Handles the complete pipeline with error checking and progress tracking.

## 📋 Data Format

Each JSON file contains a complete PubMed record with fields like:

```json
{
  "PMID": "36789123",
  "TI": "Title of the paper",
  "AB": "Abstract text...",
  "AU": ["Author 1", "Author 2"],
  "JT": "Journal Title",
  "DP": "2023",
  "MH": ["MeSH Term 1", "MeSH Term 2"],
  "PT": ["Publication Type"],
  "SO": "Journal. 2023;45(2):123-456."
}
```

## ⚠️ Important Notes

1. **Large Scale Operation**: This downloads from ALL journals - expect weeks of runtime
2. **Storage Requirements**: Plan for 50-100 GB of storage
3. **Network Stability**: Use on stable internet connection (supports resume)
4. **NCBI Compliance**: Respects NCBI rate limits and requires email registration
5. **Resume Capability**: All scripts can resume from interruption

## 🎯 Focus Areas

For faster, targeted downloads:

```bash
# Medical specialties (examples)
--subject "Dentistry"
--subject "Cardiology" 
--subject "Neurology"
--subject "Oncology"
--subject "Pediatrics"

# Basic sciences
--subject "Biochemistry"
--subject "Microbiology"
--subject "Pharmacology"
```

## 💡 Tips for Large Downloads

1. **Use a server/cloud instance** for reliability
2. **Start with one subject** to test the pipeline
3. **Monitor disk space** - growth is ~1-2 GB per day
4. **Use tmux/screen** to prevent interruption:
   ```bash
   tmux new-session -d -s nlm_download
   tmux send-keys -t nlm_download "python run_nlm_journals_download.py --email your@email.com" Enter
   ```

## 🆘 Troubleshooting

**"esearch: command not found"**
```bash
conda install -c bioconda entrez-direct
```

**"Download failed" errors**
- Check internet connection
- Verify NCBI email is valid
- Try adding `--api-key` for higher rate limits

**Disk full errors**
- Monitor with `df -h`
- Consider downloading by subject to manage size

**Resume interrupted downloads**
- Just re-run the same command - it skips existing files

## 📧 Support

- Based on existing OralEvidenceDB PubMed pipeline
- Uses same JSON format as your other projects
- Ready for import into any database system

---

**🎉 Happy downloading! This will give you a comprehensive dataset of all medical/scientific literature organized exactly as you requested.**
