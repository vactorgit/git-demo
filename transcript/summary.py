"""Optional AI summary of a transcript, using Claude. Needs ANTHROPIC_API_KEY."""

import os

import anthropic

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = (
    "You summarize YouTube video transcripts for someone deciding whether to watch, "
    "or who wants the key points without watching. Write in plain, friendly English. "
    "Auto-generated captions contain mistakes; read through them. "
    "Only state what the transcript says. Do not add facts from outside it."
)

USER_PROMPT = """\
Summarize this transcript of the YouTube video "{title}".

Format:
- One short paragraph (2-3 sentences) saying what the video is about.
- Then "Key points:" and 4 to 8 bullet points, each one sentence, in the order they come up. Start each bullet with the timestamp it comes from in [m:ss] form.

Transcript (each line starts with its timestamp):
{transcript}"""


class SummaryError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def summarize(transcript_with_times: str, title: str | None) -> str:
    if not available():
        raise SummaryError("AI summaries are off. Add ANTHROPIC_API_KEY to the .env file to turn them on.", 501)

    client = anthropic.Anthropic()
    try:
        # Streaming keeps long transcripts clear of HTTP timeouts.
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT.format(title=title or "Untitled", transcript=transcript_with_times),
                }
            ],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise SummaryError("The Anthropic API key is invalid. Check ANTHROPIC_API_KEY in .env.", 502)
    except anthropic.RateLimitError:
        raise SummaryError("Too many summary requests right now. Wait a minute and try again.", 429)
    except anthropic.BadRequestError as e:
        raise SummaryError(f"Claude couldn't summarize this transcript: {e.message}", 502)
    except anthropic.APIStatusError as e:
        raise SummaryError(f"Claude API error ({e.status_code}). Try again later.", 502)
    except anthropic.APIConnectionError:
        raise SummaryError("Couldn't reach the Claude API. Check the internet connection.", 502)

    if message.stop_reason == "refusal":
        raise SummaryError("Claude declined to summarize this video.", 422)

    text = "".join(b.text for b in message.content if b.type == "text").strip()
    if not text:
        raise SummaryError("Claude returned an empty summary. Try again.", 502)
    return text
