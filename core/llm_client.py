"""
core/llm_client.py — LangGraph version
=======================================
Stripped down to LOCAL-ONLY (Qwen2.5-Coder via Ollama).
Gemini and Groq backends removed.

In the LangGraph pipeline this module is NOT called directly —
the coder_node handles the Ollama call itself.
This module is kept for standalone / testing use.
"""

import ollama
from core.tools import get_shape_blueprint, CAD_TOOLS_SCHEMA


def generate_response(prompt_text: str, force_tool: str = "") -> str | None:
    """
    Calls Qwen2.5-Coder via Ollama.

    Parameters
    ----------
    prompt_text : str
        The fully-assembled JSON prompt string from the planner node.
    force_tool  : str
        If non-empty, the blueprint for this shape type is injected as a
        system message before the user message (bypasses Ollama tool-calling,
        which is unreliable for 7B models).

    Returns
    -------
    str | None
        Raw LLM response text, or None on failure.
    """
    messages = [{"role": "user", "content": prompt_text}]

    # ── Blueprint injection (fast path) ─────────────────────────────────────────
    if force_tool:
        blueprint_code = get_shape_blueprint(force_tool)
        messages.insert(0, {
            "role": "system",
            "content": (
                f"Base your design on this functional blueprint:\n{blueprint_code}\n\n"
                "CRITICAL: This is a SYNTAX EXAMPLE only. You MUST adjust ALL dimensions, "
                "coordinates, and logic to match the user request exactly. "
                "Do not copy the blueprint dimensions blindly."
            ),
        })
        try:
            resp = ollama.chat(model="qwen2.5-coder", messages=messages)
            return resp.message.content
        except Exception as e:
            print(f"[Ollama Error] {e}")
            return None

    # ── Autonomous tool-calling (slow path fallback) ─────────────────────────────
    try:
        response = ollama.chat(
            model="qwen2.5-coder",
            messages=messages,
            tools=CAD_TOOLS_SCHEMA,
        )

        if response.message.tool_calls:
            messages.append(response.message)
            for tool in response.message.tool_calls:
                if tool.function.name == "get_shape_blueprint":
                    shape = tool.function.arguments.get("shape_type", "")
                    blueprint_code = get_shape_blueprint(shape)
                    messages.append({
                        "role": "tool",
                        "content": (
                            f"{blueprint_code}\n\n"
                            "CRITICAL: Adjust ALL dimensions and logic to the user request."
                        ),
                        "name": tool.function.name,
                    })
            final = ollama.chat(model="qwen2.5-coder", messages=messages)
            return final.message.content

        return response.message.content

    except Exception as e:
        print(f"[Ollama Error] {e}")
        return None
