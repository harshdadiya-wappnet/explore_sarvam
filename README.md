# Exploring Sarvam AI

This repository contains small, practical examples for building with Sarvam AI:
- direct chat completion calls using the Sarvam SDK
- an OpenAI-compatible local bridge server backed by Sarvam
- a client script that talks to that bridge through the OpenAI SDK

## Prerequisites

- Python (project metadata currently declares `>=3.14` in `pyproject.toml`)
- A valid Sarvam API key

## Setup

1. Clone the repository:
```sh
git clone <your-repo-url>
cd explore_sarvam
```

2. Create your environment file:
```sh
cp .env.example .env
```
Then set your key in `.env`:
```env
SARVAM_API_KEY=your_actual_key
```

3. Install dependencies (choose one):

Using `uv`:
```sh
uv venv
source .venv/bin/activate
uv sync
```

Using `pip`:
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install fastapi uvicorn openai
```

## Project Structure

```text
.
├── README.md
├── pyproject.toml
├── requirements.txt
└── learning/
    ├── simple_usage.py
    ├── openai_chat_completion_server.py
    └── simple_usage_using_openai.py
```

## Usage

### 1. Direct Sarvam SDK chat loop

Run:
```sh
python -m learning.simple_usage
```

What it does:
- reads `SARVAM_API_KEY` from `.env`
- sends chat completion requests through the `sarvamai` SDK
- runs an interactive CLI loop until you type `exit`, `quit`, or `q`

### 2. Start OpenAI-compatible bridge server

Run:
```sh
python -m learning.openai_chat_completion_server
```

The server starts at `http://localhost:8000` and exposes:
- `GET /v1/models`
- `POST /v1/chat/completions`

It accepts OpenAI-style chat completion requests and forwards them to Sarvam.

### 3. Use OpenAI SDK client against the local bridge

In a second terminal (with the same virtual env active), run:
```sh
python learning/simple_usage_using_openai.py
```

This script uses:
- `base_url="http://localhost:8000"`
- `api_key=$SARVAM_API_KEY`
- `model="sarvam-m"`

## Quick API Check (optional)

With the bridge server running:
```sh
curl -s http://localhost:8000/v1/models
```

Example chat request:
```sh
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $SARVAM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sarvam-m",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hello in one line."}
    ]
  }'
```

## Notes

- If you are using only `requirements.txt`, install extra runtime packages for the bridge/client (`fastapi`, `uvicorn`, `openai`) as shown above.
- Keep `.env` out of version control.
