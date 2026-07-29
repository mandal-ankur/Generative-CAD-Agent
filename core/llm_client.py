"""
core/llm_client.py — LangGraph version
=======================================
Local inference via MLX (Apple Silicon).
Model: mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

In the LangGraph pipeline this module is NOT called directly —
the coder_node handles the MLX call itself.
This module is kept for standalone / testing use.
"""

from core.tools import get_shape_blueprint

# ── Lazy singleton — model is heavy, load once per process ────────────────────
_model = None
_tokenizer = None
MODEL_ID = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"


def _load():
    global _model, _tokenizer
    if _model is None:
        from mlx_lm import load
        print(f"[MLX] Loading model: {MODEL_ID}")
        _model, _tokenizer = load(MODEL_ID)
        print("[MLX] Model loaded.")
    return _model, _tokenizer


def _chat(messages: list[dict], max_tokens: int = 4096) -> str | None:
    """
    Converts a list of {role, content} messages into a single prompt string
    using the tokenizer's chat template, then runs MLX generation.
    """
    try:
        from mlx_lm import generate

        model, tokenizer = _load()

        # Apply the model's built-in chat template (handles system/user/assistant roles)
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
        )
        return response
    except Exception as e:
        print(f"[MLX Error] {e}")
        return None


def generate_response(prompt_text: str, force_tool: str = "") -> str | None:
    """
    Calls Qwen2.5-Coder-7B-Instruct via MLX (4-bit quantised).

    Parameters
    ----------
    prompt_text : str
        The fully-assembled JSON prompt string from the planner node.
    force_tool  : str
        If non-empty, the blueprint for this shape type is injected as a
        system message before the user message.

    Returns
    -------
    str | None
        Raw LLM response text, or None on failure.
    """
    messages = [{"role": "user", "content": prompt_text}]

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

    return _chat(messages)
