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
```

## Manual Setup (Windows/No-Nix)

**Prerequisites:** Python 3.10+

**Setup:**
```bash
git clone <repository-url>  
cd mailreactor
pip install uv
uv venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```