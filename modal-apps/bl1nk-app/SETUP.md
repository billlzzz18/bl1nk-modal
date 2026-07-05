# Required Dependencies

## Base Images

### bl1nk-rust:latest
This image must be built locally before deploying modal-sandbox. It includes:
- Rust toolchain
- Node.js
- GitHub CLI
- Claude CLI

**Build command:**
```bash
cd /data/data/com.termux/files/home/modal/modal-images
modal run build_bl1nk_rust.py
```

## Secrets

### GitHub PAT
Create a Modal secret for GitHub operations:
```bash
modal secret new github-pat --value=<your-token>
```

## Verification

```bash
cd /data/data/com.termux/files/home/modal/modal-apps/modal-sandbox
modal deploy modal_app.py --name modal-sandbox-v2.1
```
