# graphrag-mcp

MCP server for [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — exposes knowledge graph search as [Model Context Protocol](https://modelcontextprotocol.io) tools usable in Claude Code, OpenAI Codex, Hermes, and any MCP-compatible client.

## Tools

| Tool | Best for |
|---|---|
| `global_search` | Broad/thematic questions across the whole corpus |
| `local_search` | Entity-focused queries (people, orgs, events, places) |
| `drift_search` | Exploratory traversal — discovering unexpected connections |
| `basic_search` | Fast vector/keyword lookup for simple factual queries |

## Prerequisites

1. A built GraphRAG index (run `graphrag index --root <dir>` first)
2. Python 3.11–3.13

## Installation

```bash
# Via pip
pip install graphrag-mcp

# Via uv
uv tool install graphrag-mcp

# Via pipx
pipx install graphrag-mcp
```

The npm package is a thin launcher that delegates to the Python package:

```bash
npm install -g graphrag-mcp
# or use directly with npx (no install needed)
npx graphrag-mcp --root /path/to/project
```

## Configuration

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `GRAPHRAG_ROOT` | Yes (or `--root`) | Path to the graphrag project directory containing `settings.yaml` |
| `GRAPHRAG_DATA` | No | Override for the output/index data directory |
| `GRAPHRAG_MCP_CMD` | No | Override the Python launch command entirely (npm launcher only) |

## Usage

### Claude Code

Add to your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "npx",
      "args": ["graphrag-mcp", "--root", "/path/to/your/graphrag/project"]
    }
  }
}
```

Or register via CLI:

```bash
claude mcp add graphrag -- npx graphrag-mcp --root /path/to/your/graphrag/project
```

### OpenAI Codex

Add to your Codex MCP configuration:

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "npx",
      "args": ["graphrag-mcp", "--root", "/path/to/your/graphrag/project"]
    }
  }
}
```

### Hermes

Add to your Hermes MCP configuration:

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "npx",
      "args": ["graphrag-mcp", "--root", "/path/to/your/graphrag/project"]
    }
  }
}
```

### Direct Python (no npm)

```bash
# stdio (for MCP clients)
graphrag-mcp --root /path/to/project

# SSE transport (for HTTP-based clients)
graphrag-mcp --root /path/to/project --transport sse --port 8011

# python -m form
python -m graphrag_mcp --root /path/to/project

# With GRAPHRAG_ROOT env var
export GRAPHRAG_ROOT=/path/to/project
graphrag-mcp
```

## Quick start example

```bash
# 1. Initialise and index a project
mkdir my-project && mkdir my-project/input
cp my-documents/*.txt my-project/input/
graphrag init --root my-project
# Edit my-project/.env to add your API key
graphrag index --root my-project

# 2. Start the MCP server
export GRAPHRAG_ROOT=./my-project
graphrag-mcp
```

## Tool parameters

### `global_search`
| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | The question or search query |
| `community_level` | int\|null | `null` | Community hierarchy level (null = dynamic) |
| `response_type` | string | `"Multiple Paragraphs"` | Response format |

### `local_search`
| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | The question or search query |
| `community_level` | int | `2` | Community hierarchy level |
| `response_type` | string | `"Multiple Paragraphs"` | Response format |

### `drift_search`
| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | The question or search query |
| `community_level` | int | `2` | Community hierarchy level |
| `response_type` | string | `"Multiple Paragraphs"` | Response format |

### `basic_search`
| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | The question or search query |
| `response_type` | string | `"Multiple Paragraphs"` | Response format |

**`response_type` options:** `"Multiple Paragraphs"`, `"Single Paragraph"`, `"List of 3-7 Points"`, `"Single Page"`, `"Multi-Page Report"`

## Publishing

Tags trigger automatic publishing to both npm and PyPI via GitHub Actions:

```bash
# Bump versions in both package.json and pyproject.toml, then:
git tag mcp-v3.1.0
git push origin mcp-v3.1.0
```

### Required secrets

| Secret | Where | Description |
|---|---|---|
| `NPM_TOKEN` | GitHub repo secrets | npm access token with publish rights |
| `PYPI_TOKEN` | GitHub repo secrets | PyPI API token (or use OIDC trusted publishing) |

## License

MIT
