"""
langgraph_pipeline.py
=====================
Intent-Grounded CAD — LangGraph Implementation
-----------------------------------------------
Replaces the imperative for-loop in backend.py with a proper
LangGraph StateGraph where each agent is a node and the retry
loop is a conditional edge.

Graph topology
--------------
START
  │
  ▼
planner_node       ← intent extraction + RAG + blueprint selection + JSON prompt assembly
  │
  ▼
coder_node         ← Qwen2.5-Coder via Ollama (blueprint injected via system message)
  │
  ▼
executor_node      ← regex extract code, guardrails intercept, exec(), auto-grounding
  │
  ▼
validator_node     ← 9-layer Physics Engine
  │
  ├─ PASS ──────► exporter_node ──► END
  └─ FAIL (attempt < MAX_RETRIES) ──► planner_node  [rebuild prompt + retry]
  └─ FAIL (attempt = MAX_RETRIES) ──► END            [give up]
"""

import os
import re
import json
import sys
import math

from typing import TypedDict, Optional, List, Any
from langgraph.graph import StateGraph, END

from prompts import PROMPT_LOCAL
from core.validators import extract_design_intent_llm, validate_geometry
from core.rag_manager import retrieve_context
from core.guardrails import get_smart_feedback
from core.tools import get_shape_blueprint

MAX_RETRIES = 15
CAD_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CAD")



#  SHARED STATE SCHEMA

class CADState(TypedDict):
    # Inputs
    user_prompt:        str
    prompt_id:          str
    run_dir:            str

    # Planner outputs
    design_intent:      dict
    rag_context:        List[str]
    requires_blueprint: str
    llm_prompt:         str
    output_dir:         str

    # Retry counters
    attempt:            int
    error_history:      List[dict]
    syntax_errors:      int
    physics_errors:     int

    # Coder outputs
    llm_response:       Optional[str]
    code_block:         Optional[str]

    # Executor outputs
    final_part:         Optional[Any]
    exec_error:         Optional[str]

    # Validator outputs
    is_valid:           bool
    validation_report:  dict

    # Exporter outputs
    step_path:          Optional[str]
    stl_path:           Optional[str]
    success:            bool
    final_error:        Optional[str]



#  NODE 1 — PLANNER

def planner_node(state: CADState) -> dict:
    prompt  = state["user_prompt"]
    p_lower = prompt.lower()

    # 1. Intent extraction
    design_intent = extract_design_intent_llm(prompt)

    # 2. RAG retrieval
    rag_context = retrieve_context(prompt, k=2)

    # 3. Blueprint routing
    rb = ""
    if   "sphere"     in p_lower:                                                   rb = "sphere"
    elif "stand"      in p_lower or "cantilever" in p_lower:                        rb = "cantilever"
    elif "bracket"    in p_lower:                                                   rb = "bracket"
    elif design_intent.get("is_container"):                                         rb = "hollow_container"
    elif "overhang"   in p_lower or "floating" in p_lower or "balcony" in p_lower:  rb = "overhang_support"
    elif "cone"       in p_lower:                                                   rb = "cone"
    elif "cube"       in p_lower or "box" in p_lower or "plate" in p_lower or "block" in p_lower: rb = "cube"
    elif "cylinder"   in p_lower or "disk" in p_lower:                             rb = "cylinder"
    elif "gear"       in p_lower:                                                   rb = "gear"
    elif "pyramid"    in p_lower:                                                   rb = "pyramid"

    blueprint_text = get_shape_blueprint(rb) if rb else ""

    # 4. Assemble JSON prompt (includes error_history on retries)
    prompt_data = {
        "system_instructions":    PROMPT_LOCAL.strip(),
        "retrieved_documentation": "\n\n".join(rag_context) if rag_context else "None",
        "blueprint":              blueprint_text or "None",
        "user_request":           prompt,
        "formatting_rules":       "CRITICAL: Output ONLY the raw Python script inside ```python ... ``` blocks.",
    }
    if state.get("error_history"):
        prompt_data["error_history"]     = state["error_history"]
        prompt_data["current_objective"] = (
            "You failed the last attempt. Analyse the error, fix your code mathematically, "
            "and output ONLY the revised Python script. Do not repeat the same code."
        )

    # 5. Build output directory: CAD/<prompt_slug>/
    def _slugify(text: str, max_len: int = 40) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return slug[:max_len] or "part"

    slug    = _slugify(prompt)
    out_dir = os.path.join(CAD_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    return {
        "design_intent":      design_intent,
        "rag_context":        rag_context,
        "requires_blueprint": rb,
        "llm_prompt":         json.dumps(prompt_data, indent=2),
        "output_dir":         out_dir,
    }



#  NODE 2 — CODER

def coder_node(state: CADState) -> dict:
    import ollama

    messages = [{"role": "user", "content": state["llm_prompt"]}]

    if state.get("requires_blueprint"):
        blueprint_code = get_shape_blueprint(state["requires_blueprint"])
        messages.insert(0, {
            "role": "system",
            "content": (
                f"Base your design on this functional blueprint:\n{blueprint_code}\n\n"
                "CRITICAL: Adjust ALL dimensions and logic to match the user request. "
                "Do not copy the blueprint dimensions blindly."
            ),
        })

    try:
        resp = ollama.chat(model="qwen2.5-coder", messages=messages)
        llm_response = resp.message.content
    except Exception as e:
        llm_response = None

    return {
        "llm_response": llm_response,
        "attempt":      state.get("attempt", 0) + 1,
    }



#  NODE 3 — EXECUTOR

def executor_node(state: CADState) -> dict:
    llm_response  = state.get("llm_response") or ""
    out_dir       = state["output_dir"]
    attempt       = state.get("attempt", 1)
    error_history = list(state.get("error_history", []))
    syntax_errors = state.get("syntax_errors", 0)

    # Extract code block
    code_block = ""
    for pattern in [r"<code>(.*?)</code>", r"```(?:python)?(.*?)```"]:
        m = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
        if m:
            code_block = m.group(1).strip()
            break
    if not code_block:
        idx = llm_response.find("from build123d import")
        if idx != -1:
            code_block = llm_response[idx:].replace("</plan>", "").strip()

    if not code_block:
        err = "FORMAT ERROR: No Python code block found. Wrap output in ```python ... ``` blocks."
        error_history.append({"attempt": attempt, "type": "FormatError", "message": err})
        return {"code_block": None, "final_part": None, "exec_error": err,
                "error_history": error_history, "syntax_errors": syntax_errors}

    code_block = code_block.replace("```python", "").replace("```", "").strip()

    # Rewrite export paths → cad.stl / cad.step
    safe = out_dir.replace("\\", "/")
    code_block = re.sub(r"export_stl\s*\([^)]+\)",
                        f"export_stl(final_part, '{safe}/cad.stl')", code_block)
    code_block = re.sub(r"export_step\s*\([^)]+\)",
                        f"export_step(final_part, '{safe}/cad.step')", code_block)

    # Clear previous outputs
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))

    exec_globals = {
        "__builtins__": __builtins__,
        "json": json, "os": os, "re": re, "math": math,
        "get_shape_blueprint": lambda *a, **k: "",
    }

    try:
        exec(code_block, exec_globals)
        final_part = exec_globals.get("final_part") or exec_globals.get("part")
        if final_part is None:
            raise ValueError("Variable 'final_part' (or 'part') was not assigned.")

        # Auto-grounding
        try:
            z_min = final_part.bounding_box().min.Z
            if abs(z_min) > 0.05:
                final_part = final_part.translate((0, 0, -z_min))
        except Exception:
            pass

        return {"code_block": code_block, "final_part": final_part,
                "exec_error": None, "error_history": error_history,
                "syntax_errors": syntax_errors}

    except Exception as e:
        syntax_errors += 1
        smart_err = get_smart_feedback(f"Python Execution Error: {e}")
        error_history.append({"attempt": attempt, "type": "SyntaxError", "message": smart_err})
        return {"code_block": code_block, "final_part": None,
                "exec_error": smart_err, "error_history": error_history,
                "syntax_errors": syntax_errors}



#  NODE 4 — VALIDATOR

def validator_node(state: CADState) -> dict:
    final_part     = state.get("final_part")
    attempt        = state.get("attempt", 1)
    error_history  = list(state.get("error_history", []))
    physics_errors = state.get("physics_errors", 0)

    if final_part is None:
        return {"is_valid": False,
                "validation_report": {"message": state.get("exec_error", "Execution failed")},
                "error_history": error_history, "physics_errors": physics_errors}

    is_valid, report = validate_geometry(
        final_part,
        intent      = state.get("design_intent", {}),
        user_prompt = state["user_prompt"],
        z_offset    = 0.0,
    )

    if not is_valid:
        physics_errors += 1
        error_history.append({"attempt": attempt, "type": "PhysicsValidation", "details": report})
        for f in os.listdir(state["output_dir"]):
            os.remove(os.path.join(state["output_dir"], f))

    return {"is_valid": is_valid, "validation_report": report,
            "error_history": error_history, "physics_errors": physics_errors}



#  NODE 5 — EXPORTER

def exporter_node(state: CADState) -> dict:
    files = os.listdir(state["output_dir"])
    step  = next((f for f in files if f.endswith(".step")), None)
    stl   = next((f for f in files if f.endswith(".stl")),  None)
    return {
        "success":     bool(step and stl),
        "step_path":   os.path.join(state["output_dir"], step) if step else None,
        "stl_path":    os.path.join(state["output_dir"], stl)  if stl  else None,
        "final_error": None,
    }



#  CONDITIONAL EDGE — retry logic

def route_after_validation(state: CADState) -> str:
    if state["is_valid"]:
        return "exporter"
    if state.get("attempt", 0) >= MAX_RETRIES:
        return END
    return "planner"     # error_history already updated; planner will rebuild prompt



#  BUILD & COMPILE GRAPH

def build_graph():
    g = StateGraph(CADState)
    g.add_node("planner",   planner_node)
    g.add_node("coder",     coder_node)
    g.add_node("executor",  executor_node)
    g.add_node("validator", validator_node)
    g.add_node("exporter",  exporter_node)

    g.set_entry_point("planner")
    g.add_edge("planner",  "coder")
    g.add_edge("coder",    "executor")
    g.add_edge("executor", "validator")
    g.add_edge("exporter", END)
    g.add_conditional_edges(
        "validator", route_after_validation,
        {"planner": "planner", "exporter": "exporter", END: END},
    )
    return g.compile()



def generate_cad_part_graph(user_prompt: str, prompt_id: str = "default") -> dict:
    app = build_graph()
    initial: CADState = {
        "user_prompt": user_prompt, "prompt_id": str(prompt_id), "run_dir": "",
        "design_intent": {}, "rag_context": [], "requires_blueprint": "",
        "llm_prompt": "", "output_dir": "",
        "attempt": 0, "error_history": [], "syntax_errors": 0, "physics_errors": 0,
        "llm_response": None, "code_block": None, "final_part": None, "exec_error": None,
        "is_valid": False, "validation_report": {},
        "step_path": None, "stl_path": None, "success": False, "final_error": None,
    }
    final = app.invoke(initial)
    return {
        "success":        final.get("success", False),
        "retries":        final.get("attempt", 0),
        "step":           final.get("step_path"),
        "stl":            final.get("stl_path"),
        "final_error":    final.get("final_error"),
        "history":        final.get("error_history", []),
        "syntax_errors":  final.get("syntax_errors", 0),
        "physics_errors": final.get("physics_errors", 0),
    }


if __name__ == "__main__":
    result = generate_cad_part_graph(
        user_prompt="Make a hollow cylindrical cup with 15mm outer radius and 2mm walls",
        prompt_id="test_001",
    )
    print(json.dumps(result, indent=2, default=str))
