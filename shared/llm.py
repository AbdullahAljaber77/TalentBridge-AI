"""
TalentBridge AI — LLM Wrapper
Single place for all LLM calls. Every agent imports from here.
Never call the Anthropic SDK directly from agent files.
"""

import json
import time
import anthropic
from shared.config import ANTHROPIC_API_KEY

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────

DEFAULT_MODEL      = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 1500

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────
# Core: single prompt → text response
# ─────────────────────────────────────────────

def call_llm(prompt: str, system: str = None,
             max_tokens: int = DEFAULT_MAX_TOKENS,
             model: str = DEFAULT_MODEL,
             retries: int = 2) -> str:
    """
    Send a single prompt to Claude and return the text response.

    Use this when you just need a plain text answer — summaries,
    explanations, or any output you will handle yourself.

    Args:
        prompt:     The user message / instruction
        system:     Optional system prompt (sets Claude's role)
        max_tokens: Max tokens in the response (default 1500)
        model:      Which Claude model to use
        retries:    How many times to retry on rate limit or error

    Returns:
        str: Claude's text response

    Example:
        summary = call_llm(
            prompt="Summarize this job description: ...",
            system="You are a job market analyst."
        )
    """
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(retries + 1):
        try:
            kwargs = {
                "model":      model,
                "max_tokens": max_tokens,
                "messages":   messages,
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            if attempt < retries:
                wait = 2 ** attempt * 5    # 5s → 10s
                print(f"[llm] Rate limit hit. Waiting {wait}s (attempt {attempt + 1}/{retries})...")
                time.sleep(wait)
            else:
                raise

        except anthropic.APIError as e:
            if attempt < retries:
                print(f"[llm] API error: {e}. Retrying in 3s...")
                time.sleep(3)
            else:
                raise RuntimeError(f"LLM API failed after {retries} retries: {e}")

    return ""


# ─────────────────────────────────────────────
# Structured: single prompt → JSON dict
# ─────────────────────────────────────────────

def call_llm_json(prompt: str, system: str = None,
                  required_keys: list[str] = None,
                  max_tokens: int = DEFAULT_MAX_TOKENS,
                  model: str = DEFAULT_MODEL,
                  retries: int = 2) -> dict:
    """
    Send a prompt to Claude and return a parsed JSON dictionary.
    Use this whenever an agent needs structured output.

    Handles:
    - Stripping markdown code fences Claude sometimes adds
    - Retrying if JSON is malformed
    - Validating that required keys are present in the response

    Args:
        prompt:        The user message / instruction
        system:        Optional system prompt
        required_keys: List of keys that MUST be in the response.
                       If missing, Claude is told what went wrong and retried.
                       Example: ["extracted_skills", "experience_level"]
        max_tokens:    Max tokens in the response
        model:         Which Claude model to use
        retries:       How many times to retry on any failure

    Returns:
        dict: Parsed JSON from Claude's response

    Raises:
        ValueError: If valid JSON with required keys is not returned after retries

    Example:
        result = call_llm_json(
            prompt="Extract skills from this job: ...",
            system="You are a job analyst.",
            required_keys=["extracted_skills", "experience_level", "job_type"]
        )
        skills = result["extracted_skills"]
    """
    json_system = (
        (system or "") +
        "\nALWAYS respond with valid JSON only. "
        "No markdown, no explanation, no code blocks. Just raw JSON."
    )

    last_error = ""

    for attempt in range(retries + 1):
        # On retry: tell Claude exactly what went wrong
        if attempt > 0 and last_error:
            retry_prompt = (
                f"{prompt}\n\n"
                f"Your previous response had this problem: {last_error}\n"
                f"Fix it and return valid JSON only."
            )
        else:
            retry_prompt = prompt

        raw = call_llm(retry_prompt, system=json_system, max_tokens=max_tokens, model=model)

        # Strip markdown code fences if Claude added them anyway
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            # parts[1] is the content between the first pair of fences
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        # Try to parse as JSON
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_error = f"Response was not valid JSON: {e}. Raw response was: {raw[:200]}"
            if attempt < retries:
                print(f"[llm] JSON parse failed (attempt {attempt + 1}). Retrying with feedback...")
                continue
            else:
                raise ValueError(f"Claude did not return valid JSON after {retries} retries.\n"
                                 f"Last raw response:\n{raw}")

        # Validate required keys are present
        if required_keys:
            missing = [k for k in required_keys if k not in parsed]
            if missing:
                last_error = f"JSON was valid but missing required keys: {missing}"
                if attempt < retries:
                    print(f"[llm] Missing keys {missing} (attempt {attempt + 1}). Retrying with feedback...")
                    continue
                else:
                    raise ValueError(f"Claude's JSON was missing required keys {missing} "
                                     f"after {retries} retries.\nLast response: {parsed}")

        return parsed

    return {}


# ─────────────────────────────────────────────
# Structured input: dict → JSON response
# ─────────────────────────────────────────────

def call_llm_with_data(instruction: str, data: dict, system: str = None,
                        required_keys: list[str] = None,
                        max_tokens: int = DEFAULT_MAX_TOKENS,
                        model: str = DEFAULT_MODEL,
                        retries: int = 2) -> dict:
    """
    Send structured input data to Claude and return a parsed JSON dict.
    Use this when the input itself is structured — not just a plain string.

    Instead of building messy f-strings to inject data into prompts,
    pass the data as a dict and this function formats it cleanly for Claude.

    Args:
        instruction:   What you want Claude to do with the data.
        data:          The structured input data as a Python dict.
        system:        Optional system prompt
        required_keys: Keys that must exist in Claude's JSON response.
        max_tokens, model, retries: same as other functions.

    Returns:
        dict: Claude's response parsed as JSON

    Example — Agent 01 analyzing a job posting:
        result = call_llm_with_data(
            instruction="Analyze this job posting and extract the required fields.",
            data={
                "job_title":   "Data Scientist",
                "company":     "Saudi Aramco",
                "location":    "Dhahran",
                "description": "We are seeking a Data Scientist..."
            },
            system=build_system_prompt("job analyst", "Extract structured data."),
            required_keys=["extracted_skills", "experience_level", "job_type"]
        )

    Example — Agent 06 generating an email:
        result = call_llm_with_data(
            instruction="Generate a personalized outreach email using this context.",
            data={
                "company_name":    "NEOM",
                "company_type":    "Large Enterprise",
                "contact_name":    "Sarah Johnson",
                "recent_news":     "NEOM opened a new AI research center",
                "student_name":    "Ahmed Al-Rashidi",
                "student_skills":  ["Python", "LangChain", "RAG"],
                "tone":            "Formal",
                "call_to_action":  "Schedule a 15-minute call"
            },
            system=build_system_prompt("email writer", "Write personalized outreach emails."),
            required_keys=["subject", "body"]
        )
    """
    # Serialize the data dict to a clean, readable JSON string
    data_str = json.dumps(data, indent=2, ensure_ascii=False)

    # Build the full prompt: instruction + structured data block
    prompt = (
        f"{instruction}\n\n"
        f"Here is the input data:\n"
        f"```json\n{data_str}\n```\n\n"
        f"Respond with valid JSON only."
    )

    return call_llm_json(
        prompt=prompt,
        system=system,
        required_keys=required_keys,
        max_tokens=max_tokens,
        model=model,
        retries=retries
    )


# ─────────────────────────────────────────────
# Multi-turn: conversation history → response
# ─────────────────────────────────────────────

def call_llm_conversation(messages: list[dict], system: str = None,
                           max_tokens: int = DEFAULT_MAX_TOKENS,
                           model: str = DEFAULT_MODEL,
                           retries: int = 2) -> str:
    """
    Send a full conversation history to Claude and get the next response.
    Use this when you need multi-turn dialogue — not just a single prompt.

    The messages list must alternate between "user" and "assistant" roles,
    and must start with a "user" message.

    Args:
        messages: List of message dicts, each with "role" and "content".
                  role must be "user" or "assistant".
        system:   Optional system prompt
        max_tokens, model, retries: same as call_llm()

    Returns:
        str: Claude's next response text

    Example — Scheduling Agent building a meeting email iteratively:

        messages = [
            {"role": "user",      "content": "Draft a meeting request to NEOM HR."},
            {"role": "assistant", "content": "Here's a draft: Dear Ms. Johnson..."},
            {"role": "user",      "content": "Make it shorter and more formal."},
        ]
        revised = call_llm_conversation(messages, system="You are an email writer.")
        # Claude now responds with the revised version, aware of the full conversation
    """
    for attempt in range(retries + 1):
        try:
            kwargs = {
                "model":      model,
                "max_tokens": max_tokens,
                "messages":   messages,
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            if attempt < retries:
                wait = 2 ** attempt * 5
                print(f"[llm] Rate limit hit. Waiting {wait}s (attempt {attempt + 1}/{retries})...")
                time.sleep(wait)
            else:
                raise

        except anthropic.APIError as e:
            if attempt < retries:
                time.sleep(3)
            else:
                raise RuntimeError(f"LLM conversation call failed after {retries} retries: {e}")

    return ""


# ─────────────────────────────────────────────
# Helper: build consistent system prompts
# ─────────────────────────────────────────────

def build_system_prompt(role: str, instructions: str) -> str:
    """
    Build a consistent system prompt for any agent.

    Args:
        role:         What Claude should act as. E.g. "job posting analyst"
        instructions: The specific task instructions for this agent.

    Returns:
        str: A complete system prompt string

    Example:
        system = build_system_prompt(
            role="email response classifier",
            instructions="Classify replies as Interested, Neutral, Negative, or Auto-reply."
        )
    """
    return (
        f"You are an expert {role} working for TalentBridge AI, "
        f"an employer outreach platform for a training academy in Saudi Arabia. "
        f"You help connect talented graduates with employers across the Kingdom.\n\n"
        f"{instructions}\n\n"
        f"Always be precise, professional, and grounded in the data provided."
    )