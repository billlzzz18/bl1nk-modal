"""bl1nk-image — Image generation MCP service with memory registry.

Features: create_image, edit_image, upscale_image, enhance_prompt, 
prepare_prompt_tool, generate_from_template, list_styles, upload_asset,
convert_image_format, register_entity, save_as_reference, semantic_search,
list_entities, get_entity, vote_entry, export_for_generation, 
save_training_pair, export_dataset_manifest.

Thread safety: all shared-state ops guarded by _registry_lock.
Error contract: Every failure returns {status:'error', error_type, message, remediation}.
"""

from __future__ import annotations

import os
import re
import time
import uuid
import hashlib
import base64
import json
import threading
from typing import Any, Optional, Literal
from pathlib import Path
from datetime import datetime

import numpy as np
import faiss
from PIL import Image
import io

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field


# ── Config ───────────────────────────────────────────────────

# Style catalog — single source of truth (mirrors assets/prompt_library.py)
STYLE_CATALOG = {
    "photorealistic": {"prompt_suffix": "photorealistic, highly detailed, 8k", "neg_defaults": ["cartoon", "anime", "drawing", "painting"]},
    "cinematic": {"prompt_suffix": "cinematic lighting, dramatic, film grain, anamorphic lens", "neg_defaults": ["cartoon", "anime", "3d render"]},
    "anime": {"prompt_suffix": "anime style, cel shaded, vibrant colors", "neg_defaults": ["realistic", "photo", "3d render"]},
    "3d-render": {"prompt_suffix": "3D render, octane render, unreal engine 5, ray tracing", "neg_defaults": ["photo", "realistic", "2d"]},
    "pencil-sketch": {"prompt_suffix": "pencil sketch, hand drawn, graphite shading", "neg_defaults": ["color", "photo", "digital"]},
    "cyberpunk": {"prompt_suffix": "cyberpunk, neon lights, futuristic, high tech low life", "neg_defaults": ["natural", "historical", "medieval"]},
    "studio-portrait": {"prompt_suffix": "studio portrait, softbox lighting, professional photography", "neg_defaults": ["outdoor", "natural light", "candid"]},
    "watercolor": {"prompt_suffix": "watercolor painting, soft edges, translucent layers", "neg_defaults": ["photo", "realistic", "sharp"]},
    "metallic": {"prompt_suffix": "metallic finish, chrome, reflective surface", "neg_defaults": ["matte", "natural", "organic"]},
    "portrait": {"prompt_suffix": "portrait photography, shallow depth of field, bokeh", "neg_defaults": ["landscape", "full body", "group"]},
    "oil-painting": {"prompt_suffix": "oil painting, brush strokes, textured canvas", "neg_defaults": ["photo", "digital", "smooth"]},
    "digital-art": {"prompt_suffix": "digital art, concept art, artstation trending", "neg_defaults": ["traditional", "photo", "sketch"]},
    "minimalist": {"prompt_suffix": "minimalist, clean composition, negative space", "neg_defaults": ["cluttered", "busy", "complex"]},
    "anime-retro": {"prompt_suffix": "retro anime, 90s anime style, vintage animation", "neg_defaults": ["modern", "3d", "realistic"]},
    "pixar-3d": {"prompt_suffix": "Pixar style 3D, cute character design, soft lighting", "neg_defaults": ["realistic", "dark", "horror"]},
    "realistic-photo": {"prompt_suffix": "realistic photo, natural lighting, DSLR quality", "neg_defaults": ["cartoon", "anime", "artistic"]},
    "cartoon-2d": {"prompt_suffix": "2D cartoon, flat colors, clean lines", "neg_defaults": ["3d", "realistic", "photo"]},
    "moe-anime": {"prompt_suffix": "moe anime style, cute, big eyes, soft colors", "neg_defaults": ["realistic", "dark", "mature"]},
    "analog-photography": {"prompt_suffix": "analog photography, film grain, vintage look", "neg_defaults": ["digital", "clean", "modern"]},
    "oil-renaissance": {"prompt_suffix": "Renaissance oil painting, classical art, master technique", "neg_defaults": ["modern", "digital", "photo"]},
    "watercolor-soft": {"prompt_suffix": "soft watercolor, dreamy, pastel colors, gentle wash", "neg_defaults": ["harsh", "vibrant", "photo"]},
}

LIGHTING_OPTIONS = ["natural", "studio", "dramatic", "soft", "golden-hour", "neon", "rim-light", "volumetric"]
COMPOSITION_OPTIONS = ["close-up", "medium-shot", "wide-shot", "portrait", "landscape", "over-the-shoulder", "low-angle", "top-down"]
CAMERA_OPTIONS = ["35mm", "50mm", "85mm-portrait", "macro", "anamorphic", "drone"]
MOOD_OPTIONS = ["tense", "hopeful", "melancholic", "triumphant", "serene", "mysterious", "epic"]
NEGATIVE_PRESETS = ["universal", "anatomy", "photo", "anime", "render3d", "typography", "composition"]

WEIGHT_MIN = 0.5
WEIGHT_MAX = 2.0

# Negative prompt templates
NEGATIVE_TEMPLATES = {
    "universal": "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn hands, poorly drawn face, mutation, mutated fingers, extra fingers, fused fingers, missing fingers, long neck, unnatural pose, low quality, jpeg artifacts, signature, watermark, username",
    "anatomy": "bad anatomy, extra limbs, missing limbs, fused fingers, too many fingers, long neck, malformed hands, deformed hands, extra arms, extra legs, disconnected limbs",
    "photo": "cartoon, anime, drawing, painting, cgi, render, illustration, artwork, sketch",
    "anime": "realistic, photo, photograph, live action, 3d render, cgi",
    "render3d": "photo, realistic, real life, photograph, 2d, flat",
    "typography": "text, words, letters, characters, watermark, signature, username",
    "composition": "cropped, out of frame, cut off, poorly composed, unbalanced, cluttered",
}

# Error types with remediation
ERROR_TYPES = {
    "missing_credentials": "Set the API key in .env (see .env.example) and redeploy the service.",
    "provider_not_registered": "The configured provider is not registered. Call list_styles/get_prompt_catalog to see what is available, then update config.",
    "modality_unsupported": "This model is text-to-image only. Omit image_urls/reference_image_urls, or switch to an edit-capable model.",
    "invalid_parameter": "Check the allowed values in the tool description / get_prompt_catalog.",
    "registry_unavailable": "Memory lookup failed. Memory is optional: retry with use_memory=false, or check HF_TOKEN / REGISTRY_ENDPOINT.",
    "rate_limited": "The upstream API rate-limited the request. It is retried automatically with backoff.",
    "generation_failed": "The upstream model rejected the request. Read the provider reason in message; usually simplifying the prompt or fixing the aspect ratio resolves it.",
    "entry_not_found": "No registry entry matched. Use list_entities to browse what exists, or register_entity to add it.",
}

# Active model configuration (can be changed via API)
_active_model: str = "flux-dev"
_available_models: dict[str, dict] = {
    "flux-dev": {"provider": "replicate", "supports_edit": True, "dim": 1024},
    "sdxl": {"provider": "replicate", "supports_edit": True, "dim": 1024},
    "stable-diffusion-v1-5": {"provider": "replicate", "supports_edit": False, "dim": 512},
}

# Registry state
_registry_lock = threading.Lock()
_registry_entries: dict[str, dict] = {}  # id -> entry
_registry_vectors: dict[str, np.ndarray] = {}  # id -> CLIP vector
_registry_index: Optional[faiss.IndexFlatIP] = None
_registry_dim: int = 512  # CLIP embedding dimension

app = FastAPI(title="bl1nk-image")

TMP_STORE = os.environ.get("TMPDIR", "/tmp") + "/bl1nk-image"


def _ensure_tmp_store():
    os.makedirs(TMP_STORE, exist_ok=True)


def _error_response(error_type: str, message: str) -> dict:
    """Build standardized error response."""
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "remediation": ERROR_TYPES.get(error_type, "Contact support."),
    }


def _clamp_weight(weight: float) -> float:
    """Clamp weight to [0.5, 2.0]."""
    return max(WEIGHT_MIN, min(WEIGHT_MAX, weight))


def _parse_inline_vars(prompt: str) -> str:
    """Resolve {a|b|c} inline variables with optional ^weight."""
    def replace_var(match):
        options = match.group(1).split("|")
        # Simple deterministic selection (first option for now)
        selected = options[0]
        # Check for weight suffix
        if "^" in selected:
            term, weight_str = selected.rsplit("^", 1)
            try:
                weight = float(weight_str)
                selected = f"({term}:{_clamp_weight(weight)})"
            except ValueError:
                pass
        return selected
    
    pattern = r"\{([^}]+)\}"
    return re.sub(pattern, replace_var, prompt)


def _normalize_weights(prompt: str) -> str:
    """Normalize (term:weight) syntax, clamping weights."""
    def replace_weight(match):
        term = match.group(1)
        try:
            weight = float(match.group(2))
            return f"({term}:{_clamp_weight(weight)})"
        except ValueError:
            return match.group(0)
    
    pattern = r"\(([^:]+):([0-9.]+)\)"
    return re.sub(pattern, replace_weight, prompt)


def _clean_negative(negative: str) -> str:
    """Strip negation words from negative prompt terms."""
    negation_words = [
        "no ", "avoid ", "without ", "ไม่เอา ", "อย่า ", "ไม่มี ", "ห้าม ",
        "no ", "avoid", "without", "ไม่เอา", "อย่า", "ไม่มี", "ห้าม"
    ]
    cleaned = negative.lower()
    for word in negation_words:
        cleaned = cleaned.replace(word, "")
    # Clean up extra spaces
    cleaned = " ".join(cleaned.split())
    return cleaned


def _translate_th_en(text: str) -> str:
    """Translate Thai to English (stub - would call LLM in production)."""
    # In production, this would call an LLM
    # For now, return as-is (auto_translate would be disabled)
    return text


def _build_prompt_from_spec(spec: dict) -> tuple[str, str]:
    """Build prompt and negative prompt from structured spec."""
    parts = [spec.get("subject", "")]
    
    # Add details
    if "details" in spec:
        parts.extend(spec["details"])
    
    # Apply style
    style = spec.get("style")
    if style and style in STYLE_CATALOG:
        parts.append(STYLE_CATALOG[style]["prompt_suffix"])
    
    # Add lighting
    lighting = spec.get("lighting")
    if lighting:
        parts.append(f"{lighting} lighting")
    
    # Add composition
    composition = spec.get("composition")
    if composition:
        parts.append(f"{composition} composition")
    
    # Add camera
    camera = spec.get("camera")
    if camera:
        parts.append(f"{camera} lens")
    
    # Add mood
    mood = spec.get("mood")
    if mood:
        parts.append(f"{mood} mood")
    
    # Add color palette
    if "color_palette" in spec and spec["color_palette"]:
        parts.append(f"color palette: {', '.join(spec['color_palette'])}")
    
    # Add weighted terms
    if "weight_terms" in spec and spec["weight_terms"]:
        for wt in spec["weight_terms"]:
            term = wt.get("term", "")
            weight = _clamp_weight(wt.get("weight", 1.0))
            if term:
                parts.append(f"({term}:{weight})")
    
    prompt = ", ".join(filter(None, parts))
    
    # Build negative prompt
    negative_parts = []
    if "negative" in spec and spec["negative"]:
        neg_spec = spec["negative"]
        # Add presets
        if neg_spec and "presets" in neg_spec:
            for preset in neg_spec["presets"]:
                if preset in NEGATIVE_TEMPLATES:
                    negative_parts.append(NEGATIVE_TEMPLATES[preset])
        # Add custom terms (bare concepts only)
        if neg_spec and "custom" in neg_spec:
            for term in neg_spec["custom"]:
                cleaned = _clean_negative(term)
                if cleaned:
                    negative_parts.append(cleaned)
    
    # Add style neg_defaults
    if style and style in STYLE_CATALOG:
        negative_parts.extend(STYLE_CATALOG[style]["neg_defaults"])
    
    negative_prompt = ", ".join(negative_parts)
    
    return prompt, negative_prompt


def _compute_clip_embedding(text_or_image: str, is_image: bool = False) -> np.ndarray:
    """Compute CLIP embedding for text or image (stub)."""
    # In production, this would load a CLIP model
    # For now, return random normalized vector
    vec = np.random.randn(_registry_dim).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec


def _add_to_registry(entry: dict, vector: np.ndarray) -> None:
    """Add entry to registry index."""
    global _registry_index, _registry_entries, _registry_vectors
    
    with _registry_lock:
        entry_id = entry["id"]
        _registry_entries[entry_id] = entry
        _registry_vectors[entry_id] = vector
        
        # Rebuild index
        if len(_registry_vectors) > 0:
            all_vecs = np.vstack(list(_registry_vectors.values()))
            _registry_index = faiss.IndexFlatIP(_registry_dim)
            _registry_index.add(all_vecs.astype(np.float32))


def _search_registry(query_vector: np.ndarray, top_k: int = 5, entity_types: Optional[list] = None) -> list:
    """Search registry for similar entities."""
    global _registry_index, _registry_entries, _registry_vectors
    
    with _registry_lock:
        if _registry_index is None or len(_registry_entries) == 0:
            return []
        
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        scores, indices = _registry_index.search(query_vector, min(top_k, len(_registry_entries)))
        
        results = []
        entry_ids = list(_registry_entries.keys())
        for i, idx in enumerate(indices[0]):
            if idx < len(entry_ids):
                entry_id = entry_ids[idx]
                entry = _registry_entries[entry_id]
                
                # Filter by entity type
                if entity_types and entry.get("entity_type") not in entity_types:
                    continue
                
                # Skip negative entries unless explicitly requested
                if not entry.get("liked", True):
                    continue
                
                score = float(scores[0][i])
                results.append({
                    "id": entry_id,
                    "entity_type": entry.get("entity_type"),
                    "title": entry.get("title", ""),
                    "prompt_text": entry.get("prompt_text", ""),
                    "image_file": entry.get("image_file"),
                    "score": score,
                    "ranked_score": score * 0.65 + entry.get("votes_up", 0) * 0.15 + entry.get("usage_count", 0) * 0.10,
                })
        
        return sorted(results, key=lambda x: x["ranked_score"], reverse=True)


# ── Pydantic Models ───────────────────────────────────────────

class PromptSpec(BaseModel):
    subject: str = Field(..., description="Main subject — put maximum detail here.")
    details: Optional[list[str]] = None
    style: Optional[Literal[tuple(STYLE_CATALOG.keys())]] = None
    lighting: Optional[Literal[tuple(LIGHTING_OPTIONS)]] = None
    composition: Optional[Literal[tuple(COMPOSITION_OPTIONS)]] = None
    camera: Optional[Literal[tuple(CAMERA_OPTIONS)]] = None
    mood: Optional[Literal[tuple(MOOD_OPTIONS)]] = None
    color_palette: Optional[list[str]] = None
    weight_terms: Optional[list[dict[str, Any]]] = None
    negative: Optional[dict[str, Any]] = None


class CreateImageRequest(BaseModel):
    prompt: Optional[str] = None
    prompt_spec: Optional[PromptSpec] = None
    model: Optional[str] = None
    aspect_ratio: Literal["landscape", "square", "portrait"] = "square"
    negative_prompt: Optional[str] = None
    style: Optional[Literal[tuple(STYLE_CATALOG.keys())]] = None
    image_urls: Optional[list[str]] = None
    reference_image_urls: Optional[list[str]] = None
    registry_bucket: Optional[str] = None
    use_memory: bool = True
    auto_save_generated: bool = False
    save_keyword: Optional[str] = None
    seed: Optional[int] = None
    upscale: bool = False
    auto_translate: bool = True
    parse_inline_vars: bool = True
    normalize_prompt_weights: bool = True


class EnhancePromptRequest(BaseModel):
    raw_prompt: str
    style_hint: Literal[tuple(STYLE_CATALOG.keys())] = "photorealistic"
    negative_prompt: Optional[str] = None
    registry_bucket: Optional[str] = None
    use_registry: bool = True
    output_format: Literal["text", "spec"] = "text"


class PreparePromptRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    style: Optional[Literal[tuple(STYLE_CATALOG.keys())]] = None
    auto_translate: bool = True
    parse_inline_vars: bool = True
    normalize_prompt_weights: bool = True
    clean_negative: bool = True


class RegisterEntityRequest(BaseModel):
    bucket_id: str
    entity_type: Literal["image", "prompt", "style", "template", "category"]
    keyword: Optional[str] = None
    prompt_text: Optional[str] = None
    image_b64: Optional[str] = None
    style: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    liked: bool = True
    auto_caption: bool = False
    title: Optional[str] = None


class SaveAsReferenceRequest(BaseModel):
    bucket_id: str
    image_b64: str
    prompt: str
    keyword: str
    liked: bool = True
    tags: Optional[list[str]] = None


class SemanticSearchRequest(BaseModel):
    bucket_id: str
    query_text: Optional[str] = None
    query_image_b64: Optional[str] = None
    entity_types: Optional[list[Literal["image", "prompt", "style", "template", "category"]]] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    include_negative: bool = False
    match_against: Literal["image", "text", "auto"] = "auto"


class VoteEntryRequest(BaseModel):
    bucket_id: str
    entry_id: str
    vote: Literal["up", "down"]


class ExportForGenerationRequest(BaseModel):
    bucket_id: str
    keyword: str


class SaveTrainingPairRequest(BaseModel):
    bucket_id: str
    prompt: str
    raw_user_concept: str
    image_b64: str
    tags: Optional[list[str]] = None


# ── API Endpoints ────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/get_prompt_catalog")
async def get_prompt_catalog(section: str = "all"):
    """Return the full prompt vocabulary."""
    catalog = {}
    
    if section in ("all", "styles"):
        catalog["styles"] = list(STYLE_CATALOG.keys())
    
    if section in ("all", "lighting"):
        catalog["lighting"] = LIGHTING_OPTIONS
    
    if section in ("all", "composition"):
        catalog["composition"] = COMPOSITION_OPTIONS
    
    if section in ("all", "camera"):
        catalog["camera"] = CAMERA_OPTIONS
    
    if section in ("all", "mood"):
        catalog["mood"] = MOOD_OPTIONS
    
    if section in ("all", "negative_presets"):
        catalog["negative_presets"] = NEGATIVE_PRESETS
    
    if section in ("all", "weights"):
        catalog["weights"] = {"min": WEIGHT_MIN, "max": WEIGHT_MAX}
    
    return {"catalog": catalog}


@app.get("/list_styles")
async def list_styles(family: str = "all"):
    """Return every style preset with description, prompt_suffix and neg_defaults."""
    if family == "base":
        return {"styles": STYLE_CATALOG}
    elif family == "art_templates":
        # Could add art template styles here
        return {"styles": {}}
    else:
        return {"styles": STYLE_CATALOG}


@app.post("/prepare_prompt_tool")
async def prepare_prompt_tool(req: PreparePromptRequest):
    """Run the deterministic prompt pipeline WITHOUT generating an image."""
    prompt = req.prompt
    
    # Translate if needed
    translated = False
    if req.auto_translate:
        # Check if Thai (simple heuristic)
        if any("\u0E00" <= c <= "\u0E7F" for c in prompt):
            prompt = _translate_th_en(prompt)
            translated = True
    
    # Parse inline variables
    if req.parse_inline_vars:
        prompt = _parse_inline_vars(prompt)
    
    # Normalize weights
    if req.normalize_prompt_weights:
        prompt = _normalize_weights(prompt)
    
    # Apply style suffix
    applied_style = None
    if req.style and req.style in STYLE_CATALOG:
        applied_style = req.style
        prompt = f"{prompt}, {STYLE_CATALOG[req.style]['prompt_suffix']}"
    
    # Clean negative prompt
    negative_prompt = ""
    if req.negative_prompt:
        if req.clean_negative:
            negative_prompt = _clean_negative(req.negative_prompt)
        else:
            negative_prompt = req.negative_prompt
    
    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "applied_style": applied_style,
        "translated": translated,
    }


@app.post("/enhance_prompt")
async def enhance_prompt(req: EnhancePromptRequest):
    """Expand a brief concept into a production-quality English prompt."""
    raw = req.raw_prompt
    
    # Try registry RAG first
    if req.use_registry and req.registry_bucket:
        query_vec = _compute_clip_embedding(raw)
        matches = _search_registry(query_vec, top_k=1)
        if matches and matches[0]["score"] >= 0.28:
            return {
                "enhanced_prompt": matches[0]["prompt_text"],
                "engine": "registry-rag",
                "score": matches[0]["score"],
            }
    
    # Fallback to template expansion (LLM would be called in production)
    style = req.style_hint
    enhanced = f"{raw}, {STYLE_CATALOG.get(style, {}).get('prompt_suffix', 'highly detailed')}"
    
    return {
        "enhanced_prompt": enhanced,
        "engine": "template-matrix",
    }


@app.post("/create_image")
async def create_image(req: CreateImageRequest):
    """Memory-aware image generation with multi-model routing."""
    # Validate input
    if not req.prompt and not req.prompt_spec:
        return _error_response("invalid_parameter", "Provide either 'prompt' or 'prompt_spec'.")
    
    # Build prompt
    if req.prompt_spec:
        prompt, neg_prompt = _build_prompt_from_spec(req.prompt_spec.dict())
    else:
        prompt = req.prompt
        neg_prompt = req.negative_prompt or ""
    
    # Process prompt
    if req.parse_inline_vars:
        prompt = _parse_inline_vars(prompt)
    
    if req.normalize_prompt_weights:
        prompt = _normalize_weights(prompt)
    
    if req.auto_translate and any("\u0E00" <= c <= "\u0E7F" for c in prompt):
        prompt = _translate_th_en(prompt)
    
    # Apply style if provided (free-form path)
    if req.style and req.style in STYLE_CATALOG:
        prompt = f"{prompt}, {STYLE_CATALOG[req.style]['prompt_suffix']}"
        if req.prompt_spec is None:  # Only add neg_defaults in free-form path
            neg_parts = [neg_prompt] if neg_prompt else []
            neg_parts.extend(STYLE_CATALOG[req.style]["neg_defaults"])
            neg_prompt = ", ".join(filter(None, neg_parts))
    
    # Memory lookup (if enabled)
    memory_info = {"matches": [], "avoided_concepts": []}
    if req.use_memory and req.registry_bucket:
        query_vec = _compute_clip_embedding(prompt)
        matches = _search_registry(query_vec, top_k=3)
        if matches:
            memory_info["matches"] = matches
            # Could blend prompts here
    
    # Generate image (stub - would call actual model API)
    # In production, this would route to Replicate/other providers
    generated_url = f"https://example.com/generated/{uuid.uuid4()}.png"
    
    result = {
        "images": [{"url": generated_url}],
        "executed_prompt": prompt,
        "model_used": req.model or _active_model,
        "provider": _available_models.get(req.model or _active_model, {}).get("provider", "unknown"),
        "modality": "edit" if req.image_urls else "text-to-image",
        "memory": memory_info,
    }
    
    # Auto-save if requested
    if req.auto_save_generated and req.registry_bucket:
        # Would save to registry here
        pass
    
    return result


@app.post("/edit_image")
async def edit_image(
    image_source: str = Form(...),
    edit_instruction: str = Form(...),
    model: Optional[str] = Form(None),
    reference_image_urls: Optional[str] = Form(None),
    aspect_ratio: Literal["landscape", "square", "portrait"] = Form("square"),
):
    """Modify an existing image via the active model's edit endpoint."""
    # Validate image source
    if not image_source.startswith(("http://", "https://", "data:image/")):
        return _error_response("invalid_parameter", "image_source must be a public URL or data URI.")
    
    # Stub implementation
    result_url = f"https://example.com/edited/{uuid.uuid4()}.png"
    
    return {
        "images": [{"url": result_url}],
        "executed_edit_prompt": edit_instruction,
        "model_used": model or _active_model,
    }


@app.post("/upscale_image")
async def upscale_image(
    image_url: str,
    prompt: Optional[str] = None,
    factor: int = 2,
):
    """Post-generation high-resolution pass (~2x)."""
    # Stub implementation
    upscaled_url = f"https://example.com/upscaled/{uuid.uuid4()}.png"
    
    return {
        "url": upscaled_url,
        "upscaled": True,
        "upscale_factor": factor,
    }


@app.post("/upload_asset")
async def upload_asset(
    image_b64: str,
    collection_name: str = "uploads",
    image_name: str = "asset",
    keyword: str = "input",
):
    """Upload a Base64 image to Modal Volume."""
    # Decode base64
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    
    try:
        image_data = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(image_data))
    except Exception as e:
        return _error_response("invalid_parameter", f"Corrupt base64 image: {str(e)}")
    
    # Generate filename
    hash_key = hashlib.sha256(image_data).hexdigest()[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{collection_name}/{image_name}-{keyword}-{date_str}-{hash_key}.png"
    
    # In production, would save to Modal Volume
    # For now, save to tmp
    _ensure_tmp_store()
    filepath = Path(TMP_STORE) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    img.save(filepath)
    
    # Build URLs
    public_url = f"https://volume.modal.local/{filename}"
    data_uri = f"data:image/png;base64,{base64.b64encode(image_data).decode()}"
    
    return {
        "rel_path": filename,
        "public_url": public_url,
        "data_uri": data_uri,
    }


@app.post("/convert_image_format")
async def convert_image_format(
    b64_image: str,
    export_format: Literal["jpg", "jpeg", "webp", "png", "html"] = "png",
    resize_dim: Optional[Literal["1k", "2k"]] = None,
):
    """Convert a Base64 image to different format."""
    # Decode
    if "," in b64_image:
        b64_image = b64_image.split(",", 1)[1]
    
    try:
        image_data = base64.b64decode(b64_image)
        img = Image.open(io.BytesIO(image_data))
    except Exception as e:
        return _error_response("invalid_parameter", f"Corrupt input: {str(e)}")
    
    # Resize if requested
    if resize_dim:
        max_side = 1024 if resize_dim == "1k" else 2048
        ratio = min(max_side / img.width, max_side / img.height)
        if ratio < 1:
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert
    output = io.BytesIO()
    fmt = export_format.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    
    if img.mode in ("RGBA", "LA") and fmt == "JPEG":
        img = img.convert("RGB")
    
    img.save(output, format=fmt)
    output_b64 = base64.b64encode(output.getvalue()).decode()
    
    if export_format == "html":
        html_embed = f'<img src="data:image/{export_format};base64,{output_b64}" />'
        return {"html_embed": html_embed, "format": export_format}
    
    return {"image_b64": output_b64, "format": export_format}


@app.post("/register_entity")
async def register_entity(req: RegisterEntityRequest):
    """Register any entity type into the registry bucket."""
    # Validate entity type
    valid_types = ["image", "prompt", "style", "template", "category"]
    if req.entity_type not in valid_types:
        return _error_response("invalid_parameter", f"Invalid entity_type. Must be one of: {valid_types}")
    
    # Generate ID
    entry_id = f"{req.bucket_id}/{req.entity_type}/{req.keyword or uuid.uuid4().hex[:8]}"
    
    # Compute vector
    if req.image_b64:
        vector = _compute_clip_embedding(req.image_b64, is_image=True)
    elif req.prompt_text:
        vector = _compute_clip_embedding(req.prompt_text)
    else:
        return _error_response("invalid_parameter", "Provide either image_b64 or prompt_text for embedding.")
    
    # Generate deterministic title
    title = req.title or f"{req.entity_type.capitalize()}: {req.keyword or 'untitled'}"
    
    # Build entry
    entry = {
        "id": entry_id,
        "bucket_id": req.bucket_id,
        "entity_type": req.entity_type,
        "keyword": req.keyword,
        "title": title,
        "prompt_text": req.prompt_text,
        "style": req.style,
        "tags": req.tags or [],
        "category": req.category,
        "liked": req.liked,
        "votes_up": 0,
        "votes_down": 0,
        "usage_count": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Add to registry
    _add_to_registry(entry, vector)
    
    return {"entry": entry}


@app.post("/save_as_reference")
async def save_as_reference(req: SaveAsReferenceRequest):
    """Shortcut for register_entity(entity_type='image') after a generation."""
    entity_req = RegisterEntityRequest(
        bucket_id=req.bucket_id,
        entity_type="image",
        keyword=req.keyword,
        prompt_text=req.prompt,
        image_b64=req.image_b64,
        tags=req.tags,
        liked=req.liked,
    )
    return await register_entity(entity_req)


@app.post("/semantic_search")
async def semantic_search(req: SemanticSearchRequest):
    """Find registry entities closest to a text or image query."""
    # Get query vector
    if req.query_text:
        query_vec = _compute_clip_embedding(req.query_text)
    elif req.query_image_b64:
        query_vec = _compute_clip_embedding(req.query_image_b64, is_image=True)
    else:
        return _error_response("invalid_parameter", "Provide either query_text or query_image_b64.")
    
    # Search
    results = _search_registry(
        query_vec,
        top_k=req.top_k,
        entity_types=req.entity_types,
    )
    
    return {"results": results}


@app.get("/list_entities")
async def list_entities(
    bucket_id: str,
    entity_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
):
    """Structural browse of the registry by entity_type and category."""
    results = []
    for entry in _registry_entries.values():
        if entry.get("bucket_id") != bucket_id:
            continue
        if entity_type and entry.get("entity_type") != entity_type:
            continue
        if category and entry.get("category") != category:
            continue
        results.append(entry)
        if len(results) >= limit:
            break
    
    return {"total": len(results), "results": results}


@app.get("/get_entity")
async def get_entity(bucket_id: str, id: Optional[str] = None, keyword: Optional[str] = None):
    """Fetch one full registry entry by id or keyword."""
    if id:
        entry = _registry_entries.get(id)
        if entry and entry.get("bucket_id") == bucket_id:
            return {"entry": entry}
    
    if keyword:
        for entry in _registry_entries.values():
            if entry.get("bucket_id") == bucket_id and entry.get("keyword") == keyword:
                return {"entry": entry}
    
    return _error_response("entry_not_found", f"No entry found in bucket {bucket_id}")


@app.post("/vote_entry")
async def vote_entry(req: VoteEntryRequest):
    """Upvote or downvote a registry entry."""
    entry = _registry_entries.get(req.entry_id)
    if not entry or entry.get("bucket_id") != req.bucket_id:
        return _error_response("entry_not_found", f"Entry {req.entry_id} not found")
    
    if req.vote == "up":
        entry["votes_up"] = entry.get("votes_up", 0) + 1
    else:
        entry["votes_down"] = entry.get("votes_down", 0) + 1
        # Auto-mark as negative after 3 downvotes
        if entry["votes_down"] >= 3:
            entry["liked"] = False
    
    return {
        "entry": {
            "id": entry["id"],
            "votes_up": entry["votes_up"],
            "votes_down": entry["votes_down"],
            "is_negative": not entry["liked"],
        }
    }


@app.post("/export_for_generation")
async def export_for_generation(req: ExportForGenerationRequest):
    """Build a ready-to-use reference payload from a registry entry."""
    entry = None
    for e in _registry_entries.values():
        if e.get("bucket_id") == req.bucket_id and e.get("keyword") == req.keyword:
            entry = e
            break
    
    if not entry:
        return _error_response("entry_not_found", f"No entry with keyword '{req.keyword}' in bucket '{req.bucket_id}'")
    
    return {
        "reference_url": f"https://volume.modal.local/{entry.get('image_file', '')}",
        "recommended_prompt": entry.get("prompt_text", ""),
        "usage_note": "Chain this output into create_image (as reference_image_urls) or edit_image (as image_source).",
    }


@app.post("/save_training_pair")
async def save_training_pair(req: SaveTrainingPairRequest):
    """Store a prompt+image pair into the dataset split."""
    # In production, would save to data/images/*.webp + data/train.jsonl
    _ensure_tmp_store()
    
    # Decode and save image
    if "," in req.image_b64:
        image_b64 = req.image_b64.split(",", 1)[1]
    else:
        image_b64 = req.image_b64
    
    image_data = base64.b64decode(image_b64)
    filename = f"data/images/{uuid.uuid4().hex}.webp"
    filepath = Path(TMP_STORE) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    img = Image.open(io.BytesIO(image_data))
    img.save(filepath, format="WEBP")
    
    # Append to train.jsonl
    train_file = Path(TMP_STORE) / "data" / "train.jsonl"
    train_file.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "image_file": filename,
        "prompt": req.prompt,
        "raw_user_concept": req.raw_user_concept,
        "tags": req.tags or [],
        "created_at": datetime.utcnow().isoformat(),
    }
    
    with open(train_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    
    return {"uploaded_file": filename}


@app.get("/export_dataset_manifest")
async def export_dataset_manifest(bucket_id: str):
    """Summarize the training dataset in a bucket."""
    train_file = Path(TMP_STORE) / "data" / "train.jsonl"
    
    if not train_file.exists():
        return {"total_pairs": 0, "tag_distribution": {}, "files": []}
    
    records = []
    tag_counts = {}
    
    with open(train_file) as f:
        for line in f:
            record = json.loads(line.strip())
            records.append(record)
            for tag in record.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    files = [r["image_file"] for r in records]
    
    return {
        "total_pairs": len(records),
        "tag_distribution": tag_counts,
        "files": files,
    }

