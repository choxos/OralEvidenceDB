# OpenAlex Oral Health Papers Download

This directory contains scripts to download oral health papers from OpenAlex API.

## 🦷 What it downloads

**Comprehensive Oral Health Research**
- **Search Terms**: dental, dentistry, oral health, oral medicine, stomatology, odontology, maxillofacial, orofacial, periodontal, endodontic, orthodontic, prosthodontic, oral surgery, periodontics, endodontics, orthodontics, prosthodontics, pediatric dentistry, oral pathology, oral biology, teeth, tooth, gingiva, gums, oral cavity, dental caries, tooth decay, periodontitis, gingivitis, oral cancer, dental implant, root canal, dental restoration, dentures, braces, oral hygiene, dental materials, oral microbiology, dental radiography
- **Date Range**: From inception to 2025 (no restrictions)
- **Sources**: Title and abstract searches across all OpenAlex papers

## 📁 Directory Structure

After running, you'll get:
```
data/openalex_oral_health/
├── json_papers/
│   ├── w2768689142.json
│   ├── w2756234891.json
│   └── ... (all papers as individual JSON files)
├── by_year/
│   ├── 1950/
│   │   ├── w2768689142.json
│   │   └── ...
│   ├── 1951/
│   ├── ...
│   └── 2025/
├── download_stats.json (download statistics)
└── openalex_oral_health_download.log (download log)
```

Each JSON file contains:
- Complete OpenAlex record
- Reconstructed abstract (from inverted index)
- All metadata (authors, citations, concepts, etc.)

## 🚀 How to Run

### Simple Execution
```bash
cd /Users/choxos/Documents/GitHub/OralEvidenceDB
python scripts/download_openalex_oral_health.py
```

### With Virtual Environment
```bash
cd /Users/choxos/Documents/GitHub/OralEvidenceDB
source venv/bin/activate  # or your virtual environment
python scripts/download_openalex_oral_health.py
```

## 📊 Expected Results

- **Volume**: Hundreds of thousands of oral health papers
- **Coverage**: From historical dental research to modern oral health studies
- **Quality**: Peer-reviewed academic papers with full metadata
- **Abstracts**: Reconstructed abstracts for most papers
- **Organization**: Both flat structure and year-based organization

## 🔧 Requirements

- Python 3.6+
- `requests` library
- Internet connection
- Disk space (several GB for complete dataset)

## 📈 Features

✅ **Comprehensive Search**: 40+ oral health related terms  
✅ **No Date Limits**: Historical to current research  
✅ **Abstract Reconstruction**: Converts OpenAlex inverted index to readable text  
✅ **Dual Organization**: Both flat and year-based file structure  
✅ **Progress Tracking**: Real-time progress and statistics  
✅ **Error Handling**: Robust error handling and logging  
✅ **Rate Limiting**: Respectful API usage  
✅ **Resume Support**: Skip already downloaded papers  

## 🔍 Search Strategy

The script searches for papers containing any of these terms in **title OR abstract**:

**Core Dental Terms**: dental, dentistry, teeth, tooth  
**Medical Specialties**: oral medicine, stomatology, odontology  
**Anatomical**: maxillofacial, orofacial, oral cavity, gingiva, gums  
**Specializations**: periodontal, endodontic, orthodontic, prosthodontic  
**Procedures**: oral surgery, root canal, dental restoration, dental implant  
**Conditions**: dental caries, tooth decay, periodontitis, gingivitis, oral cancer  
**Devices/Materials**: dentures, braces, dental materials  
**Subspecialties**: pediatric dentistry, oral pathology, oral biology  
**Research Areas**: oral hygiene, oral microbiology, dental radiography  

## 💡 Usage Tips

1. **Large Dataset**: This will download a very large number of papers (potentially 500k+)
2. **Time**: Full download may take several hours to complete
3. **Space**: Ensure you have several GB of free disk space
4. **Interruption**: You can stop and restart - it will skip existing files
5. **Monitoring**: Check the log file for detailed progress and any issues

## 🔗 Integration

This complements your PubMed download:
- **PubMed**: High-precision MeSH Major Topic search (medical focus)
- **OpenAlex**: Broad comprehensive search (includes interdisciplinary research)
- **Combined**: Complete coverage of oral health research landscape

## 📋 Next Steps

After download completes:
1. Check `download_stats.json` for summary statistics
2. Explore papers by year in `by_year/` directories  
3. Use JSON files for analysis or database import
4. Consider creating import scripts for your Django database

---

**🦷 Happy researching with comprehensive oral health literature!** 📚✨
