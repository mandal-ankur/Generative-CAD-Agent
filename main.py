import streamlit as app
import time

#  PAGE CONFIG — must be first Streamlit call

app.set_page_config(
    page_title="AI CAD Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)


#  CUSTOM CSS — premium dark theme

app.markdown("""
<style>
    /* ── Global ──────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: #0d0f1a;
    }

    /* ── Sidebar — always visible, no collapse button ────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111327 0%, #0d0f1a 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
        min-width: 260px !important;
        max-width: 260px !important;
    }

    /* Hide the sidebar collapse/expand toggle arrow */
    [data-testid="stSidebarCollapseButton"],
    button[kind="header"] {
        display: none !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }

    .sidebar-title {
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 0.75rem;
        padding-left: 0.25rem;
    }

    /* History item card */
    .history-item {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
        padding: 0.65rem 0.85rem;
        margin-bottom: 0.55rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .history-item:hover {
        background: rgba(99, 102, 241, 0.12);
        border-color: rgba(99, 102, 241, 0.35);
        transform: translateX(2px);
    }

    .history-item-prompt {
        font-size: 0.82rem;
        color: #d1d5db;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 200px;
    }

    .history-item-meta {
        font-size: 0.70rem;
        color: #6b7280;
        margin-top: 0.25rem;
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    .badge-success {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(74, 222, 128, 0.2);
        border-radius: 4px;
        padding: 0.05rem 0.35rem;
        font-size: 0.65rem;
        font-weight: 600;
    }

    .badge-fail {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.2);
        border-radius: 4px;
        padding: 0.05rem 0.35rem;
        font-size: 0.65rem;
        font-weight: 600;
    }

    .badge-pending {
        background: rgba(234, 179, 8, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.2);
        border-radius: 4px;
        padding: 0.05rem 0.35rem;
        font-size: 0.65rem;
        font-weight: 600;
    }

    /* ── Main area ───────────────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #1e1b4b 0%, #111827 100%);
        border: 1px solid rgba(99,102,241,0.2);
        padding: 1.1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .main-header-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f9fafb;
    }

    .main-header-sub {
        font-size: 0.80rem;
        color: #9ca3af;
        margin-top: 0.1rem;
    }

    /* Workspace placeholder */
    .workspace-placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 400px;
        background: rgba(255,255,255,0.02);
        border: 2px dashed rgba(255,255,255,0.07);
        border-radius: 16px;
        color: #374151;
        text-align: center;
        padding: 2rem;
    }

    .workspace-placeholder-text {
        font-size: 1.05rem;
        font-weight: 500;
        color: #4b5563;
    }

    .workspace-placeholder-sub {
        font-size: 0.82rem;
        color: #374151;
        margin-top: 0.4rem;
    }

    /* Status pill */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(99,102,241,0.12);
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 999px;
        padding: 0.3rem 0.75rem;
        font-size: 0.78rem;
        color: #a5b4fc;
        font-weight: 500;
    }

    .pulse-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #818cf8;
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%       { opacity: 0.4; transform: scale(0.75); }
    }

    /* ── Bottom input bar ────────────────────────────────── */
    .input-bar-wrapper {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(0deg, #0d0f1a 70%, transparent 100%);
        padding: 1rem 1.5rem 1.5rem 1.5rem;
        z-index: 999;
    }

    .input-inner {
        max-width: 900px;
        margin: 0 auto;
        background: rgba(17, 19, 39, 0.95);
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 14px;
        padding: 0.6rem 0.6rem 0.6rem 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        backdrop-filter: blur(12px);
        box-shadow: 0 -4px 40px rgba(0,0,0,0.4), 0 0 0 1px rgba(99,102,241,0.1);
    }

    /* Override Streamlit text input inside input bar */
    .input-bar-wrapper .stTextInput > div > div > input {
        background: transparent !important;
        border: none !important;
        color: #f3f4f6 !important;
        font-size: 0.92rem !important;
        box-shadow: none !important;
        padding: 0.4rem 0 !important;
    }

    .input-bar-wrapper .stTextInput > div > div > input::placeholder {
        color: #6b7280 !important;
    }

    .input-bar-wrapper .stTextInput > div {
        border: none !important;
        box-shadow: none !important;
    }

    /* Sidebar / generic buttons (Select, Clear History, view toggles) */
    .stButton button {
        background: rgba(255,255,255,0.05) !important;
        color: #d1d5db !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 0.45rem 1.1rem !important;
        transition: all 0.2s ease !important;
        white-space: nowrap;
    }

    .stButton button:hover {
        background: rgba(99,102,241,0.15) !important;
        border-color: rgba(99,102,241,0.35) !important;
        color: #a5b4fc !important;
    }

    /* Generate (form submit) button — matches the top header */
    [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #1e1b4b 0%, #111827 100%) !important;
        color: #a5b4fc !important;
        border: 1px solid rgba(99,102,241,0.35) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 0.45rem 1.1rem !important;
        transition: all 0.2s ease !important;
        white-space: nowrap;
    }

    [data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(135deg, #2d2a6e 0%, #1a2035 100%) !important;
        border-color: rgba(99,102,241,0.6) !important;
        box-shadow: 0 0 16px rgba(99,102,241,0.25) !important;
        transform: translateY(-1px) !important;
    }

    /* Hide "Press Enter to submit" helper text */
    [data-testid="InputInstructions"],
    .stForm small { display: none !important; }

    /* ── Chat-style response cards ───────────────────────── */
    .response-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }

    .response-card-prompt {
        font-size: 0.82rem;
        font-weight: 600;
        color: #a5b4fc;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    /* ── Hide default Streamlit elements ─────────────────── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 8rem !important; }

    /* Hide every known variant of Streamlit's bottom violet stripe */
    [data-testid="stDecoration"],
    [data-testid="stBottom"],
    [data-testid="stBottomBlockContainer"],
    [data-testid="stStatusWidget"],
    .stDecorationBar,
    iframe[title="streamlit_stl"] + div { display: none !important; }

    /* Prevent horizontal scrollbar bleed */
    body { overflow-x: hidden !important; }
</style>
""", unsafe_allow_html=True)


#  SESSION STATE INIT

if "history" not in app.session_state:
    app.session_state.history = []           # list of dicts: {prompt, status, timestamp, result}
if "active_idx" not in app.session_state:
    app.session_state.active_idx = None      # which history item is focused in workspace
if "pending_prompt" not in app.session_state:
    app.session_state.pending_prompt = None
if "input_key" not in app.session_state:
    app.session_state.input_key = 0          # rotated to clear the text input after submission


#  SIDEBAR — Prompt History

with app.sidebar:
    # Logo / title
    app.markdown("""
    <div style='text-align:center; margin-bottom:1.5rem;'>
        <div style='font-size:1rem; font-weight:700; color:#f9fafb;'>CAD Agent</div>
        <div style='font-size:0.72rem; color:#6b7280;'>Intent-Grounded 3D Generator</div>
    </div>
    """, unsafe_allow_html=True)

    app.markdown('<div class="sidebar-title">Prompt History</div>', unsafe_allow_html=True)

    if not app.session_state.history:
        app.markdown("""
        <div style='text-align:center; padding: 2rem 0.5rem; color:#374151;'>
            <div style='font-size:0.80rem;'>Your prompts will<br>appear here</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for i, item in enumerate(reversed(app.session_state.history)):
            real_idx = len(app.session_state.history) - 1 - i
            status = item.get("status", "pending")
            badge_class = {"success": "badge-success", "fail": "badge-fail"}.get(status, "badge-pending")
            badge_label = {"success": "Done", "fail": "Failed"}.get(status, "Running")
            ts = item.get("timestamp", "")

            is_active = (app.session_state.active_idx == real_idx)
            border_color = "rgba(99,102,241,0.45)" if is_active else "rgba(255,255,255,0.07)"
            bg_color = "rgba(99,102,241,0.08)" if is_active else "rgba(255,255,255,0.04)"

            app.markdown(f"""
            <div class="history-item" style="border-color:{border_color}; background:{bg_color};">
                <div class="history-item-prompt" title="{item['prompt']}">{item['prompt']}</div>
                <div class="history-item-meta">
                    <span class="{badge_class}">{badge_label}</span>
                    <span>{ts}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Invisible button overlay to select this history item
            if app.button("Select", key=f"hist_{real_idx}", help=item["prompt"]):
                app.session_state.active_idx = real_idx
                app.rerun()

    # Divider + clear button
    if app.session_state.history:
        app.markdown("<br>", unsafe_allow_html=True)
        if app.button("Clear History", use_container_width=True):
            app.session_state.history = []
            app.session_state.active_idx = None
            app.rerun()



#  MAIN WORKSPACE AREA


# Header bar
app.markdown("""
<div class="main-header">
    <div>
        <div class="main-header-title">Live Workspace</div>
        <div class="main-header-sub">AI-powered 3D CAD generation with physics validation</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Process a pending prompt (submitted via the fixed bottom bar) ──
if app.session_state.pending_prompt:
    prompt = app.session_state.pending_prompt
    app.session_state.pending_prompt = None

    timestamp = time.strftime("%H:%M")
    entry = {"prompt": prompt, "status": "running", "timestamp": timestamp, "result": None}
    app.session_state.history.append(entry)
    app.session_state.active_idx = len(app.session_state.history) - 1

    # Show a live status while processing
    with app.status(f'Generating: "{prompt}"', expanded=True) as status_widget:
        app.write("**Agent 1 — Planner**: Extracting design intent…")
        time.sleep(0.4)
        app.write("**RAG Retrieval**: Fetching relevant build123d docs from ChromaDB…")
        time.sleep(0.4)
        app.write("**Agent 2 — Coder**: Sending structured JSON prompt to LLM…")
        time.sleep(0.4)
        app.write("**Retry Loop**: Validating geometry with Physics Engine…")
        time.sleep(0.4)

        # ── REAL BACKEND CALL ──
        from langgraph_pipeline import generate_cad_part_graph
        from core.logger import log_experiment

        t_start = time.time()
        result = generate_cad_part_graph(prompt, prompt_id=f"gui_{int(t_start)}")
        elapsed = round(time.time() - t_start, 2)

        # Add execution time to the result for display
        result["execution_time_sec"] = elapsed

        # Log to benchmark CSV/log
        log_experiment(
            prompt_id=f"gui_{int(t_start)}",
            prompt=prompt,
            attempts=result.get("retries", 0),
            execution_time=elapsed,
            success=result.get("success", False),
            category="GUI",
            syntax_errors=result.get("syntax_errors", 0),
            physics_errors=result.get("physics_errors", 0),
            error_history=result.get("history", []),
            final_error=result.get("final_error")
        )
        # ─────────────────────────────────────────────────────

        if result["success"]:
            status_widget.update(label="Generation complete!", state="complete", expanded=False)
            app.session_state.history[app.session_state.active_idx]["status"] = "success"
        else:
            status_widget.update(label="Generation failed", state="error", expanded=True)
            app.session_state.history[app.session_state.active_idx]["status"] = "fail"

    app.session_state.history[app.session_state.active_idx]["result"] = result
    app.rerun()


# ── Render workspace for the active history entry ──
active_idx = app.session_state.active_idx

if active_idx is None or not app.session_state.history:
    # Empty state
    app.markdown("""
    <div class="workspace-placeholder">
        <div class="workspace-placeholder-text">Your workspace is empty</div>
        <div class="workspace-placeholder-sub">Submit a prompt below to start generating 3D CAD models</div>
    </div>
    """, unsafe_allow_html=True)
else:
    entry = app.session_state.history[active_idx]
    status = entry.get("status", "pending")
    result = entry.get("result")

    # Prompt echo
    app.markdown(f"""
    <div class="response-card">
        <div class="response-card-prompt">Your prompt</div>
        <div style='font-size:0.95rem; color:#f3f4f6; font-weight:500;'>{entry['prompt']}</div>
    </div>
    """, unsafe_allow_html=True)

    if status == "running":
        app.markdown("""
        <div class="status-pill">
            <span class="pulse-dot"></span> Agent pipeline running…
        </div>
        """, unsafe_allow_html=True)

    elif status == "success" and result:
        # ── Success workspace ──────────────────────────────────
        import os

        col_a, col_b, col_c = app.columns([1, 1, 1])
        with col_a:
            app.metric("Attempts", result.get("retries", "—"))
        with col_b:
            app.metric("Time", f"{result.get('execution_time_sec', '—')}s")
        with col_c:
            app.metric("Syntax fixes", result.get("syntax_errors", 0))

        app.markdown("<br>", unsafe_allow_html=True)

        # ── Download buttons ───────────────────────────────────
        step_path = result.get("step")
        stl_path  = result.get("stl")

        dl_col1, dl_col2, _ = app.columns([1, 1, 2])
        with dl_col1:
            if step_path and os.path.exists(step_path):
                with open(step_path, "rb") as f:
                    app.download_button(
                        label="Download STEP",
                        data=f,
                        file_name=os.path.basename(step_path),
                        mime="application/octet-stream",
                        use_container_width=True,
                    )
            else:
                app.button("Download STEP (unavailable)", disabled=True, use_container_width=True)

        with dl_col2:
            if stl_path and os.path.exists(stl_path):
                with open(stl_path, "rb") as f:
                    app.download_button(
                        label="Download STL",
                        data=f,
                        file_name=os.path.basename(stl_path),
                        mime="application/sla",
                        use_container_width=True,
                    )
            else:
                app.button("Download STL (unavailable)", disabled=True, use_container_width=True)

        # ── Live 3D Viewer ─────────────────────────────────────
        if stl_path and os.path.exists(stl_path):
            app.markdown("<br>", unsafe_allow_html=True)
            app.markdown("""
            <div style='
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(99,102,241,0.2);
                border-radius: 14px;
                padding: 1rem 1.2rem 0.5rem 1.2rem;
                margin-bottom: 0.5rem;
            '>
                <div style='font-size:0.82rem; font-weight:600; color:#a5b4fc;
                            margin-bottom:0.6rem; display:flex; align-items:center; gap:0.4rem;'>
                    Live 3D Preview
                    <span style='font-size:0.70rem; color:#6b7280; font-weight:400;'>
                        — drag to rotate &nbsp;·&nbsp; scroll to zoom
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            view_mode = app.session_state.get(f"view_mode_{active_idx}", "material")

            from streamlit_stl import STLComponent
            stl_comp = STLComponent()
            stl_comp.stl_from_file(
                file_path=stl_path,
                color="#6366f1",
                material=view_mode,
                auto_rotate=False,
                opacity=1,
                shininess=120,
                cam_v_angle=30,
                cam_h_angle=-60,
                cam_distance=0,
                height=500,
                key=f"cad_preview_{active_idx}_{view_mode}",
            )

            # View-mode toggle row
            app.markdown("<br>", unsafe_allow_html=True)
            v1, v2, v3, _ = app.columns([1, 1, 1, 4])
            with v1:
                if app.button("Solid", key=f"solid_{active_idx}", use_container_width=True):
                    app.session_state[f"view_mode_{active_idx}"] = "material"
                    app.rerun()
            with v2:
                if app.button("Wireframe", key=f"wire_{active_idx}", use_container_width=True):
                    app.session_state[f"view_mode_{active_idx}"] = "wireframe"
                    app.rerun()
            with v3:
                if app.button("Flat", key=f"flat_{active_idx}", use_container_width=True):
                    app.session_state[f"view_mode_{active_idx}"] = "flat"
                    app.rerun()
        else:
            app.info("STL file not found — re-run the prompt to generate a 3D model.")

    elif status == "fail" and result:
        # ── Failure workspace ──────────────────────────────────
        app.error(f"Generation failed after {result.get('retries', '?')} attempts.")

        if result.get("final_error"):
            with app.expander("Final error details", expanded=True):
                app.code(result["final_error"], language="text")

        if result.get("history"):
            with app.expander(f"Retry log ({len(result['history'])} attempts)", expanded=False):
                for h in result["history"]:
                    attempt  = h.get("attempt", "?")
                    err_type = h.get("type", "Error")
                    msg = (
                        h.get("details", {}).get("message", "")
                        if err_type == "PhysicsValidation"
                        else h.get("message", "")
                    )
                    app.markdown(f"**Attempt {attempt}** — `{err_type}`")
                    if msg:
                        app.code(msg[:400], language="text")


#  FIXED BOTTOM INPUT BAR
#
#  Enter key support: text_input fires on_change on every keystroke including
#  Enter. We detect a submit intent via a callback that sets pending_prompt.
#  The input key is rotated after each submission so Streamlit renders a fresh
#  (empty) widget on the next rerun — this is the idiomatic way to clear a
#  text_input in Streamlit.

def _on_input_change():
    """Called on every change to the text input (including Enter)."""
    val = app.session_state.get(f"prompt_field_{app.session_state.input_key}", "").strip()
    # Streamlit fires on_change both for normal keystrokes AND for Enter.
    # We use a separate 'enter_submitted' flag set by the form submit mechanism.
    # Because st.text_input doesn't expose an "enter pressed" event directly,
    # we rely on st.form to capture Enter — see the form below.

app.markdown('<div class="input-bar-wrapper"><div class="input-inner">', unsafe_allow_html=True)

with app.container():
    with app.form(key="prompt_form", clear_on_submit=True):
        input_col, btn_col = app.columns([9, 1])
        with input_col:
            prompt_input = app.text_input(
                label="prompt",
                label_visibility="collapsed",
                placeholder="Describe the 3D part you want to create…",
                key=f"prompt_field_{app.session_state.input_key}",
            )
        with btn_col:
            submit = app.form_submit_button("Generate", use_container_width=True)

app.markdown("</div></div>", unsafe_allow_html=True)

# Handle submission (button click OR Enter key inside the form)
if submit and prompt_input.strip():
    app.session_state.pending_prompt = prompt_input.strip()
    # Rotate the key → Streamlit will render a fresh empty input on next rerun
    app.session_state.input_key += 1
    app.rerun()
