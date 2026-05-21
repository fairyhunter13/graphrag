# Copyright (c) 2024 fairyhunter13.
# Licensed under the MIT License

"""GraphRAG MCP Server.

Exposes Microsoft GraphRAG search modes as MCP tools consumable by
Claude Code, OpenAI Codex, Hermes, and any MCP-compatible client.

Configuration
-------------
GRAPHRAG_ROOT   Path to the graphrag project directory (contains settings.yaml).
GRAPHRAG_DATA   Optional override for the output/index data directory.

CLI flags (override env vars)
-----------------------------
--root   Path to the graphrag project directory.
--data   Path to the output/index data directory.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP

import graphrag.api as api
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.data_model.data_reader import DataReader
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "graphrag",
    instructions=(
        "GraphRAG knowledge graph search server.\n\n"
        "Tools:\n"
        "- global_search: broad/thematic questions across the whole corpus\n"
        "- local_search: entity-focused queries (people, orgs, places)\n"
        "- drift_search: exploratory traversal for discovering connections\n"
        "- basic_search: fast vector/keyword lookup for simple facts\n\n"
        "Always prefer global_search for 'what are the main themes' style questions "
        "and local_search for 'tell me about X' style questions."
    ),
)

# ---------------------------------------------------------------------------
# Runtime state (lazy-initialised, module-level singletons)
# ---------------------------------------------------------------------------

_config: GraphRagConfig | None = None
_table_provider: Any = None
_reader: DataReader | None = None
_cache: dict[str, pd.DataFrame | None] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args() -> dict[str, str]:
    """Parse --root and --data from sys.argv without consuming them."""
    result: dict[str, str] = {}
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in ("--root", "-r") and i + 1 < len(argv):
            result["root"] = argv[i + 1]
        elif arg in ("--data", "-d") and i + 1 < len(argv):
            result["data"] = argv[i + 1]
    return result


def _root_dir() -> Path:
    cli = _parse_args()
    root = cli.get("root") or os.environ.get("GRAPHRAG_ROOT")
    if not root:
        msg = (
            "GraphRAG root directory is required.\n"
            "Set GRAPHRAG_ROOT env var or pass --root <path>."
        )
        raise RuntimeError(msg)
    return Path(root).expanduser().resolve()


def _ensure_config() -> GraphRagConfig:
    global _config
    if _config is None:
        root = _root_dir()
        cli = _parse_args()
        overrides: dict[str, Any] = {}
        data = cli.get("data") or os.environ.get("GRAPHRAG_DATA")
        if data:
            overrides["output_storage"] = {"base_dir": data}
        _config = load_config(root_dir=root, cli_overrides=overrides or None)
        logger.info("Loaded GraphRAG config from %s", root)
    return _config


async def _ensure_reader() -> tuple[DataReader, Any]:
    global _table_provider, _reader
    if _reader is None:
        config = _ensure_config()
        storage = create_storage(config.output_storage)
        _table_provider = create_table_provider(config.table_provider, storage=storage)
        _reader = DataReader(_table_provider)
    return _reader, _table_provider


async def _load(name: str, *, optional: bool = False) -> pd.DataFrame | None:
    """Load a table DataFrame, caching after first load."""
    if name in _cache:
        return _cache[name]
    reader, provider = await _ensure_reader()
    if optional:
        exists = await provider.has(name)
        if not exists:
            _cache[name] = None
            return None
    df: pd.DataFrame = await getattr(reader, name)()
    _cache[name] = df
    logger.debug("Loaded table '%s' (%d rows)", name, len(df))
    return df


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def global_search(
    query: str,
    community_level: int | None = None,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """Search the knowledge graph for broad, thematic questions.

    Best for questions like:
    - "What are the main themes in this corpus?"
    - "Summarise the key findings about X"
    - "What patterns exist across all documents?"

    Uses map-reduce over community reports at the specified level.

    Parameters
    ----------
    query:
        The question or search query.
    community_level:
        Community hierarchy level to search (None = dynamic selection).
    response_type:
        Format of the response, e.g. "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points", "Single Page", "Multi-Page Report".
    """
    config = _ensure_config()
    entities = await _load("entities")
    communities = await _load("communities")
    community_reports = await _load("community_reports")

    response, _ = await api.global_search(
        config=config,
        entities=entities,
        communities=communities,
        community_reports=community_reports,
        community_level=community_level,
        dynamic_community_selection=community_level is None,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def local_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """Search the knowledge graph for entity-focused questions.

    Best for questions like:
    - "Tell me about [person/organization/place]"
    - "What is the relationship between X and Y?"
    - "What did [entity] do in [context]?"

    Uses entity neighbourhood context with relationship traversal.

    Parameters
    ----------
    query:
        The question or search query.
    community_level:
        Community hierarchy level for context (default: 2).
    response_type:
        Format of the response, e.g. "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points", "Single Page", "Multi-Page Report".
    """
    config = _ensure_config()
    entities = await _load("entities")
    communities = await _load("communities")
    community_reports = await _load("community_reports")
    text_units = await _load("text_units")
    relationships = await _load("relationships")
    covariates = await _load("covariates", optional=True)

    response, _ = await api.local_search(
        config=config,
        entities=entities,
        communities=communities,
        community_reports=community_reports,
        text_units=text_units,
        relationships=relationships,
        covariates=covariates,
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def drift_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """Explore the knowledge graph through iterative graph traversal.

    Best for:
    - Open-ended discovery ("What connects X to Y?")
    - Hypothesis exploration
    - Finding unexpected relationships

    Performs depth-based traversal starting from seed entities.

    Parameters
    ----------
    query:
        The question or search query.
    community_level:
        Community hierarchy level (default: 2).
    response_type:
        Format of the response, e.g. "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points", "Single Page", "Multi-Page Report".
    """
    config = _ensure_config()
    entities = await _load("entities")
    communities = await _load("communities")
    community_reports = await _load("community_reports")
    text_units = await _load("text_units")
    relationships = await _load("relationships")

    response, _ = await api.drift_search(
        config=config,
        entities=entities,
        communities=communities,
        community_reports=community_reports,
        text_units=text_units,
        relationships=relationships,
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def basic_search(
    query: str,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """Fast vector/keyword-based search over text chunks.

    Best for:
    - Simple factual lookups
    - When speed matters more than graph context
    - Direct keyword matching

    Parameters
    ----------
    query:
        The question or search query.
    response_type:
        Format of the response, e.g. "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points", "Single Page", "Multi-Page Report".
    """
    config = _ensure_config()
    text_units = await _load("text_units")

    response, _ = await api.basic_search(
        config=config,
        text_units=text_units,
        response_type=response_type,
        query=query,
    )
    return str(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the GraphRAG MCP server."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="graphrag-mcp",
        description="GraphRAG MCP Server — exposes GraphRAG search as MCP tools.",
    )
    parser.add_argument(
        "--root",
        "-r",
        metavar="DIR",
        help="GraphRAG project root directory (contains settings.yaml). "
        "Overrides GRAPHRAG_ROOT env var.",
    )
    parser.add_argument(
        "--data",
        "-d",
        metavar="DIR",
        help="Output/index data directory override. Overrides GRAPHRAG_DATA env var.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8011,
        help="Port for SSE transport (default: 8011).",
    )
    args = parser.parse_args()

    if args.root:
        os.environ.setdefault("GRAPHRAG_ROOT", args.root)
    if args.data:
        os.environ.setdefault("GRAPHRAG_DATA", args.data)

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
