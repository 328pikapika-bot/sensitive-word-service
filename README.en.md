# Sensitive Word Service

English | [简体中文](README.md)

A Flask web/API service for text screening with dictionary matching, Plus normalized matching, file text extraction, and optional model-based semantic review.

## Capabilities

- Dictionary matching includes word-boundary handling; the Plus engine normalizes selected character variants.
- Accepts text and extracts content from TXT, DOCX, and PDF files.
- Can call an OpenAI-compatible model endpoint for semantic review.

## Code and setup

`源码/app.py` provides Flask routes and text handling, `源码/sensitive_plus.py` the Plus engine, `源码/config.py` configuration, and `源码/templates/` the UI. Install `源码/requirements.txt`, configure the process environment, then run `python app.py` from `源码/`. The default port is 3309.

The app, configuration, and Plus engine were restored from this project's local archive. The default `源码/sensitive_words.example.txt` contains only two synthetic example entries. Supply your own UTF-8 dictionary for actual use.

## Configuration

Set `SENSITIVE_WORDS_PATH` for the dictionary and `LLM_API_KEY`, `LLM_API_URL`, and `LLM_MODEL_NAME` for model review. Use `源码/.env.example` as a template, but inject environment variables into the process: the app does not load `.env` automatically.

## Verification and limits

The complete business dictionary is not published. Dictionary hits and model opinions require human judgment. Before external deployment, review authentication, server-side path reads, uploads, and URL access restrictions. The HTTP server and model endpoint were not run during the 2026-11-04 public-code review.

See the [publication notes](仓库发布说明.md) for scope; local archives are excluded.
