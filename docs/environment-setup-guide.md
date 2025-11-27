# Environment Setup Guide

## Nix + direnv (Recommended)

**Prerequisites:**
- **Nix package manager:** https://nixos.org/download.html
- **direnv:** https://direnv.net/docs/installation.html

**Setup:**
```bash
git clone <repository-url>
cd mailreactor
direnv allow
# Follow quickstart instructions shown in terminal

# Verify setup:
python verify-setup.sh
```

## Manual Setup (Windows/No-Nix)

**Prerequisites:** pip

**Setup:**
```bash
git clone <repository-url>  
cd mailreactor
pip install uv
uv venv --python python3.10
.venv\Scripts\activate      # Linux: source .venv/bin/activate
uv pip install -e ".[dev]"

# Verify setup:
python verify-setup.sh
```
