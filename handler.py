import os
import pandas as pd
from primfunctions.events import Event, StartEvent, TextEvent, TextToSpeechEvent
from primfunctions.context import Context
from voicerun_completions import CompletionsClient, deserialize_conversation, UserMessage

# ── Load CSV once at startup ──────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.csv")

df = pd.read_csv(
    DATA_PATH,
    usecols=[
        "case_enquiry_id", "open_dt", "closed_dt", "on_time",
        "case_status", "case_title", "type", "department",
        "neighborhood", "location_street_name", "location_zipcode", "source"
    ],
    parse_dates=["open_dt", "closed_dt"],
    low_memory=False,
)

# ── Build a compact data summary injected into every system prompt ────────────
def build_data_summary() -> str:
    total        = len(df)
    open_cases   = int((df["case_status"] == "Open").sum())
    closed_cases = int((df["case_status"] == "Closed").sum())
    top_types    = df["type"].value_counts().head(8).to_dict()
    top_hoods    = df["neighborhood"].value_counts().head(8).to_dict()
    overdue      = int((df["on_time"] == "OVERDUE").sum())

    top_types_str = ", ".join(f"{k} ({v})" for k, v in top_types.items())
    top_hoods_str = ", ".join(f"{k} ({v})" for k, v in top_hoods.items())

    return f"""
DATASET SUMMARY (Boston 311 Service Requests):
- Total cases: {total:,}
- Open: {open_cases:,} | Closed: {closed_cases:,} | Overdue: {overdue:,}
- Top request types: {top_types_str}
- Top neighborhoods: {top_hoods_str}

QUERY CAPABILITIES:
You can answer questions about: request types, neighborhoods, open/closed/overdue
status, departments, date ranges, and specific addresses or zip codes.
When asked for a number or count, compute it from the summary above or say
you'd need to run a deeper query. Keep answers concise and voice-friendly —
no bullet points, no markdown, just natural spoken sentences.
""".strip()

DATA_SUMMARY = build_data_summary()

# ── System prompts (English + Spanish) ───────────────────────────────────────
BASE_PROMPT_EN = f"""You are a helpful Boston 311 service request assistant.
You help residents and city staff understand the status of service requests
across Boston neighborhoods. Answer questions conversationally and concisely —
your responses will be spoken aloud, so avoid lists, symbols, or formatting.
If you don't know something, say so honestly. Always respond in English.

{DATA_SUMMARY}"""

BASE_PROMPT_ES = f"""Eres un asistente útil del servicio 311 de Boston.
Ayudas a los residentes y al personal de la ciudad a entender el estado de las
solicitudes de servicio en los barrios de Boston. Responde de forma conversacional
y concisa — tus respuestas se dirán en voz alta, así que evita listas, símbolos
o formato. Si no sabes algo, dilo con honestidad. Responde siempre en español.

{DATA_SUMMARY}"""

# ── Language detection helper ─────────────────────────────────────────────────
DETECT_PROMPT = """Detect the language of the following text.
Reply with exactly one word: either "english" or "spanish". Nothing else."""

async def detect_language(text: str, api_key: str) -> str:
    """Returns 'spanish' or 'english'."""
    from voicerun_completions import generate_chat_completion
    try:
        result = await generate_chat_completion({
            "provider": "anthropic",
            "api_key": api_key,
            "model": "claude-haiku-4-5",
            "system": DETECT_PROMPT,
            "messages": [{"role": "user", "content": text}],
        })
        lang = result.message.content.strip().lower()
        return "spanish" if "spanish" in lang else "english"
    except Exception:
        return "english"

# ── Voice config per language ─────────────────────────────────────────────────
VOICES = {
    "english": "nova",
    "spanish": "jorge",   # Spanish-accented voice on VoiceRun/ElevenLabs
}

# ── Module-level completions client (keeps connections warm) ──────────────────
completions = CompletionsClient()

# ── Handler ───────────────────────────────────────────────────────────────────
async def handler(event: Event, context: Context):
    if isinstance(event, StartEvent):
        # Bilingual greeting so callers know Spanish is supported
        yield TextToSpeechEvent(
            text=(
                "Hi! I'm the Boston 311 assistant. "
                "I can answer questions about service requests across the city. "
                "You can speak to me in English or Spanish. "
                "¡Hola! También puedo ayudarte en español. "
                "What would you like to know?"
            ),
            voice=VOICES["english"],
        )

    if isinstance(event, TextEvent):
        user_message = event.data.get("text", "").strip()
        if not user_message:
            return

        api_key = context.variables.get("ANTHROPIC_API_KEY")

        # Detect language and pick the right prompt + voice
        lang    = await detect_language(user_message, api_key)
        prompt  = BASE_PROMPT_ES if lang == "spanish" else BASE_PROMPT_EN
        voice   = VOICES[lang]

        # Store detected language in session state so it persists across turns
        context.set_state({"lang": lang})

        messages = deserialize_conversation(context.get_completion_messages())
        messages.append(UserMessage(content=user_message))

        stream = await completions.generate_chat_completion_stream(
            request={
                "provider": "anthropic",
                "api_key": api_key,
                "model": "claude-haiku-4-5",
                "system": prompt,
                "messages": messages,
            },
            stream_options={"stream_sentences": True, "clean_sentences": True},
        )

        async for chunk in stream:
            if chunk.type == "content_sentence":
                yield TextToSpeechEvent(text=chunk.sentence, voice=voice)
            elif chunk.type == "response":
                messages.append(chunk.response.message)
                context.set_completion_messages(messages)
