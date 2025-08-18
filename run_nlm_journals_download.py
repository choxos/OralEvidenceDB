#!/usr/bin/env python3
"""
Master script to download and parse all NLM journals from PubMed
Handles the complete pipeline: Download → Parse → Organize
"""

import subprocess
import sys
import time
from pathlib import Path
import argparse

def run_command(cmd, description):
    """Run shell command with error handling"""
    print(f"🚀 {description}")
    print(f"   Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()
    
    try:
        if isinstance(cmd, list):
            result = subprocess.run(cmd, check=True, text=True, capture_output=False)
        else:
            result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=False)
        
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code: {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found. Make sure required tools are installed.")
        return False

def check_dependencies():
    """Check if required tools are available"""
    print("🔍 Checking dependencies...")
    
    required_tools = [
        ('esearch', 'NCBI E-utilities (install with: conda install -c bioconda entrez-direct)'),
        ('efetch', 'NCBI E-utilities (install with: conda install -c bioconda entrez-direct)'),
    ]
    
    missing_tools = []
    for tool, install_hint in required_tools:
        try:
            subprocess.run([tool, '-help'], capture_output=True, check=True)
            print(f"   ✅ {tool} found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"   ❌ {tool} not found - {install_hint}")
            missing_tools.append(tool)
    
    if missing_tools:
        print(f"\n❌ Missing required tools: {', '.join(missing_tools)}")
        print("Please install them before running this script.")
        return False
    
    print("✅ All dependencies found!\n")
    return True

def estimate_download_time():
    """Provide time estimate for the download"""
    print("⏱️  DOWNLOAD TIME ESTIMATE")
    print("=" * 50)
    print("📊 NLM Catalog contains ~16,000 journals")
    print("📅 Year range: 1940-2025 (85 years)")
    print("🔢 Estimated queries: ~1.3 million")
    print("⏱️  Rate limit: ~2 queries/second")
    print("🕐 Estimated time: ~7-10 days continuous")
    print("💾 Estimated storage: 50-100 GB")
    print()
    print("💡 Tips:")
    print("   • Use --subject to focus on specific areas")
    print("   • Script supports resuming if interrupted")
    print("   • Consider running on a server/cloud instance")
    print()

def main():
    parser = argparse.ArgumentParser(
        description='Download and parse all NLM journals from PubMed'
    )
    parser.add_argument(
        '--download-only', 
        action='store_true',
        help='Only download MEDLINE files, skip JSON parsing'
    )
    parser.add_argument(
        '--parse-only', 
        action='store_true',
        help='Only parse existing MEDLINE files to JSON, skip download'
    )
    parser.add_argument(
        '--subject', 
        type=str,
        help='Focus on specific subject area (e.g., "Dentistry")'
    )
    parser.add_argument(
        '--estimate', 
        action='store_true',
        help='Show time/storage estimates and exit'
    )
    parser.add_argument(
        '--email', 
        type=str,
        help='Your email for NCBI API (required for download)'
    )
    parser.add_argument(
        '--api-key', 
        type=str,
        help='NCBI API key (optional, increases rate limits)'
    )
    
    args = parser.parse_args()
    
    print("📚 NLM Journals Complete Pipeline")
    print("=================================")
    
    if args.estimate:
        estimate_download_time()
        return
    
    # Check dependencies
    if not args.parse_only:
        if not check_dependencies():
            sys.exit(1)
    
    # Make scripts executable
    scripts = ['download_all_nlm_journals.sh']
    for script in scripts:
        script_path = Path(script)
        if script_path.exists():
            script_path.chmod(0o755)
            print(f"✅ Made {script} executable")
    
    success_steps = []
    
    # Step 1: Download MEDLINE files
    if not args.parse_only:
        print("\n" + "="*60)
        print("STEP 1: DOWNLOAD MEDLINE FILES FROM PUBMED")
        print("="*60)
        
        if not args.email:
            print("❌ Email address is required for NCBI API")
            print("Use: --email your@email.com")
            sys.exit(1)
        
        # Update the download script with email/API key
        download_script = Path('download_all_nlm_journals.sh')
        if download_script.exists():
            content = download_script.read_text()
            content = content.replace('EMAIL="your-email@example.com"', f'EMAIL="{args.email}"')
            if args.api_key:
                content = content.replace('API_KEY=""', f'API_KEY="{args.api_key}"')
            download_script.write_text(content)
        
        if run_command('./download_all_nlm_journals.sh', 'Download MEDLINE files'):
            success_steps.append('Download')
        else:
            print("❌ Download step failed. Cannot proceed.")
            sys.exit(1)
    
    # Step 2: Parse MEDLINE to JSON
    if not args.download_only:
        print("\n" + "="*60)
        print("STEP 2: PARSE MEDLINE FILES TO JSON")
        print("="*60)
        
        parse_cmd = [sys.executable, 'parse_nlm_journals_to_json.py']
        if args.subject:
            parse_cmd.extend(['--subject', args.subject])
        parse_cmd.append('--resume')  # Always use resume mode
        
        if run_command(parse_cmd, 'Parse MEDLINE to JSON'):
            success_steps.append('Parse')
        else:
            print("❌ Parse step failed.")
            sys.exit(1)
    
    # Summary
    print("\n" + "="*60)
    print("🎉 NLM JOURNALS PIPELINE COMPLETE!")
    print("="*60)
    print(f"✅ Completed steps: {', '.join(success_steps)}")
    print()
    print("📁 Your data is organized as:")
    print("   nlm_journals_data/")
    print("   ├── [Subject_Area]/")
    print("   │   ├── [Journal_Name]/")
    print("   │   │   ├── medline/          # Raw MEDLINE files")
    print("   │   │   ├── json/             # Parsed JSON files")
    print("   │   │   │   ├── 2023/         # Papers by year")
    print("   │   │   │   ├── 2022/")
    print("   │   │   │   └── ...")
    print("   │   │   └── journal_info.txt  # Journal metadata")
    print("   │   └── ...")
    print("   └── ...")
    print()
    print("💡 You can now use these JSON files for your other projects!")

if __name__ == '__main__':
    main()
