# Boston 311 Voice Agent

A VoiceRun voice agent that answers questions about Boston 311 city service requests.

## What it does

Residents and city staff can ask natural language questions like:
- "How many open cases are there?"
- "What's the most common request type?"
- "How many overdue cases are in East Boston?"
- "Which neighborhood has the most parking complaints?"

## Project structure

```
boston-311-agent/
├── handler.py           # Agent logic — voice I/O + Claude
├── data.csv             # Boston 311 service request data
├── requirements.txt     # Python dependencies
├── .voicerun/
│   └── agent.yaml       # Agent metadata
└── README.md
```

## Setup

### 1. Install the VoiceRun CLI

```bash
pip install voicerun-cli
```

### 2. Sign in

```bash
vr signin
```

### 3. Add your Anthropic API key as a secret

```bash
vr set secret ANTHROPIC_API_KEY=your_key_here
```

### 4. Push and deploy

```bash
vr push
vr deploy production
```

### 5. Test locally (optional)

```bash
vr debug
```

## Swapping the data

Replace `data.csv` with any updated 311 export — the agent reloads it at startup.
The columns it uses are:
`case_enquiry_id`, `open_dt`, `closed_dt`, `on_time`, `case_status`,
`case_title`, `type`, `department`, `neighborhood`,
`location_street_name`, `location_zipcode`, `source`

## Changing the LLM

In `handler.py`, update the `provider` and `model` fields:
```python
"provider": "openai",   # or "anthropic", "google"
"model": "gpt-4o-mini", # or "claude-haiku-4-5", etc.
```
And swap the secret name to match (e.g. `OPENAI_API_KEY`).
