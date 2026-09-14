"""Tests for bl1nk-image MCP service."""

import pytest
import asyncio
from src.image_service import (
    app,
    get_prompt_catalog,
    list_styles,
    prepare_prompt_tool,
    PreparePromptRequest,
    create_image,
    CreateImageRequest,
    PromptSpec,
    register_entity,
    RegisterEntityRequest,
    semantic_search,
    SemanticSearchRequest,
    vote_entry,
    VoteEntryRequest,
)


@pytest.mark.asyncio
async def test_get_prompt_catalog():
    """Test getting the full prompt catalog."""
    result = await get_prompt_catalog("all")
    assert "catalog" in result
    assert "styles" in result["catalog"]
    assert "lighting" in result["catalog"]
    assert len(result["catalog"]["styles"]) == 21


@pytest.mark.asyncio
async def test_list_styles():
    """Test listing all styles."""
    result = await list_styles("all")
    assert "styles" in result
    assert len(result["styles"]) == 21
    assert "photorealistic" in result["styles"]
    assert "prompt_suffix" in result["styles"]["photorealistic"]


@pytest.mark.asyncio
async def test_prepare_prompt_tool_basic():
    """Test basic prompt preparation."""
    req = PreparePromptRequest(
        prompt="a cat sitting on a windowsill",
        style="photorealistic",
    )
    result = await prepare_prompt_tool(req)
    assert "prompt" in result
    assert "photorealistic" in result["prompt"]
    assert result["applied_style"] == "photorealistic"


@pytest.mark.asyncio
async def test_prepare_prompt_tool_weights():
    """Test weight normalization."""
    req = PreparePromptRequest(
        prompt="a dragon (fire:3.0) breathing (ice:0.3)",
        parse_inline_vars=True,
        normalize_prompt_weights=True,
    )
    result = await prepare_prompt_tool(req)
    # Weights should be clamped to [0.5, 2.0]
    assert "(fire:2.0)" in result["prompt"] or "(fire:2" in result["prompt"]
    assert "(ice:0.5)" in result["prompt"] or "(ice:0.5" in result["prompt"]


@pytest.mark.asyncio
async def test_create_image_with_spec():
    """Test image creation with structured spec."""
    spec = PromptSpec(
        subject="a futuristic cityscape",
        style="cyberpunk",
        lighting="neon",
        mood="mysterious",
    )
    req = CreateImageRequest(prompt_spec=spec, use_memory=False)
    result = await create_image(req)
    assert "images" in result
    assert len(result["images"]) > 0
    assert "executed_prompt" in result
    assert "cyberpunk" in result["executed_prompt"]


@pytest.mark.asyncio
async def test_register_and_search_entity():
    """Test entity registration and semantic search."""
    # Register an entity
    reg_req = RegisterEntityRequest(
        bucket_id="test/bucket",
        entity_type="prompt",
        keyword="test-cat",
        prompt_text="a cute cat sleeping",
        liked=True,
        tags=["cat", "sleep"],
    )
    reg_result = await register_entity(reg_req)
    assert "entry" in reg_result
    assert reg_result["entry"]["keyword"] == "test-cat"
    
    # Search for it
    search_req = SemanticSearchRequest(
        bucket_id="test/bucket",
        query_text="feline resting",
        top_k=5,
    )
    search_result = await semantic_search(search_req)
    assert "results" in search_result
    # Note: With random embeddings, we may or may not find matches


@pytest.mark.asyncio
async def test_vote_entry():
    """Test voting on entries."""
    # First register an entry
    reg_req = RegisterEntityRequest(
        bucket_id="test/vote",
        entity_type="prompt",
        keyword="vote-test",
        prompt_text="test prompt",
        liked=True,
    )
    reg_result = await register_entity(reg_req)
    entry_id = reg_result["entry"]["id"]
    
    # Upvote
    vote_req = VoteEntryRequest(bucket_id="test/vote", entry_id=entry_id, vote="up")
    vote_result = await vote_entry(vote_req)
    assert vote_result["entry"]["votes_up"] == 1
    
    # Downvote
    vote_req.vote = "down"
    vote_result = await vote_entry(vote_req)
    assert vote_result["entry"]["votes_down"] == 1
