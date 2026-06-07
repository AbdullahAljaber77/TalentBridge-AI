"""
TalentBridge AI — LLM Wrapper
Single place for all LLM calls. Every agent imports call_llm() from here.
Never call the Anthropic/OpenAI SDK directly from agent files.
"""

import json
import time
import anthropic
from shared.config import ANTHROPIC_API_KEY, OPENAI_API_KEY

# Default model — Anthropic preferred
DEFAULT_MODEL    = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 1500

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def call_llm(prompt: str, system: str = None, max_tokens: int = DEFAULT_MAX_TOKENS,
             model: str = DEFAULT_MODEL, retries: int = 2) -> str:
    """
    Send a prompt to the LLM and return the text response.
    Used by all agents for any LLM call.

    Args:
        prompt:     The user message / instruction
        system:     Optional system prompt (sets the agent's role/behavior)
        max_tokens: Max tokens in the response
        model:      LLM model to use
        retries:    Number of retries on rate limit or API error

    Returns:
        str: The LLM's text response
    """
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(retries + 1):
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            if attempt < retries:
                wait = 2 ** attempt * 5   # 5s, 10s
                print(f"Rate limit hit. Waiting {wait}s before retry {attempt + 1}...")
                time.sleep(wait)
            else:
                raise

        except anthropic.APIError as e:
            if attempt < retries:
                time.sleep(3)
            else:
                raise RuntimeError(f"LLM API error after {retries} retries: {e}")

    return ""


def call_llm_json(prompt: str, system: str = None, max_tokens: int = DEFAULT_MAX_TOKENS,
                   model: str = DEFAULT_MODEL, retries: int = 2) -> dict:
    """
    Call the LLM and parse the response as JSON.
    Use this whenever an agent needs structured output.

    Returns:
        dict: Parsed JSON from LLM response

    Raises:
        ValueError: If response cannot be parsed as JSON after retries
    """
    json_system = (system or "") + "\nALWAYS respond with valid JSON only. No markdown, no explanation, no code blocks."

    for attempt in range(retries + 1):
        raw = call_llm(prompt, system=json_system, max_tokens=max_tokens, model=model)

        # Strip markdown code fences if model adds them anyway
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt < retries:
                print(f"JSON parse failed on attempt {attempt + 1}. Retrying...")
            else:
                raise ValueError(f"LLM did not return valid JSON after {retries} retries.\nRaw response:\n{raw}")

    return {}


def build_system_prompt(role: str, instructions: str) -> str:
    """
    Helper to build consistent system prompts across all agents.

    Example:
        system = build_system_prompt(
            role="job analysis expert",
            instructions="Extract structured data from job descriptions."
        )
    """
    return f"You are an expert {role} working for TalentBridge AI, an employer outreach platform for a training academy in Saudi Arabia.\n\n{instructions}\n\nAlways be precise, professional, and grounded in the data provided."