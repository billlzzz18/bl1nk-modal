# bl1nk-image MCP Server

Image generation and memory registry service deployed on Modal.

## Features

- **Image Generation**: Multi-model routing with structured prompt validation
- **Memory Registry**: Semantic search for prompts and images using CLIP embeddings
- **Prompt Enhancement**: LLM-based expansion with template fallbacks
- **Edit/Upscale**: Post-generation image modification
- **Training Dataset**: Export pairs for fine-tuning

## Deployment

```bash
# Build the image
cd /workspace/modal-images
python build_bl1nk_image.py

# Deploy the service
cd /workspace/modal-apps/bl1nk-image
modal deploy deploy.py
```

## Environment Variables

Set these secrets in Modal:

```bash
modal secret create bl1nk-image-auth \
  HF_TOKEN=your_huggingface_token \
  OPENAI_API_KEY=your_openai_key \
  REPLICATE_API_KEY=your_replicate_key
```

## MCP Tools

The server exposes these tools via MCP:

1. `get_prompt_catalog` - Get valid styles, lighting, composition values
2. `create_image` - Generate images with memory-aware routing
3. `edit_image` - Modify existing images
4. `upscale_image` - High-resolution pass (~2x)
5. `enhance_prompt` - Expand concepts to production prompts
6. `prepare_prompt_tool` - Preview prompt pipeline output
7. `generate_from_template` - Fill weighted templates
8. `list_styles` - Browse style presets
9. `upload_asset` - Upload images to Modal Volume
10. `convert_image_format` - Convert/resize images
11. `register_entity` - Store entities in registry
12. `save_as_reference` - Save generation results
13. `semantic_search` - Find similar entities
14. `list_entities` - Browse registry structurally
15. `get_entity` - Fetch single entity
16. `vote_entry` - Upvote/downvote entries
17. `export_for_generation` - Build reference payload
18. `save_training_pair` - Store for fine-tuning
19. `export_dataset_manifest` - Summarize training data

## Error Contract

All errors return:
```json
{
  "status": "error",
  "error_type": "<type>",
  "message": "<description>",
  "remediation": "<how to fix>"
}
```

Error types: `missing_credentials`, `provider_not_registered`, `modality_unsupported`, `invalid_parameter`, `registry_unavailable`, `rate_limited`, `generation_failed`, `entry_not_found`
