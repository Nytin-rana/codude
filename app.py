import io
import json
import os
import shutil
import time
import random
import traceback
import zipfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
REGISTRY_PATH = PROJECTS_DIR / "registry.json"


def ensure_projects_dir():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.write_text("[]", encoding="utf-8")


def slugify_project(name: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "project"


def get_project_root_from_name(name: str) -> str:
    return str(PROJECTS_DIR / slugify_project(name) / "generated_project")


def load_project_registry() -> list[dict]:
    ensure_projects_dir()
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_project_registry(name: str, prompt: str) -> dict:
    ensure_projects_dir()
    slug = slugify_project(name)
    registry = load_project_registry()
    entry = {
        "name": name,
        "slug": slug,
        "prompt": prompt,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    for idx, item in enumerate(registry):
        if item.get("slug") == slug:
            registry[idx] = entry
            break
    else:
        registry.insert(0, entry)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return entry


def remove_project_from_registry(name: str) -> None:
    ensure_projects_dir()
    slug = slugify_project(name)
    registry = load_project_registry()
    registry = [item for item in registry if item.get("slug") != slug]
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def delete_project_files(name: str) -> None:
    project_dir = Path(get_project_root_from_name(name)).parent
    if project_dir.exists():
        shutil.rmtree(project_dir)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CODudE",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "previous_projects" not in st.session_state:
    registry = load_project_registry()
    st.session_state.previous_projects = [item["name"] for item in registry] or ["todo app"]
if "current_project" not in st.session_state:
    st.session_state.current_project = ""
if "prompt_text" not in st.session_state:
    st.session_state.prompt_text = ""
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False
if "delete_pending" not in st.session_state:
    st.session_state.delete_pending = ""

# ---------------------------------------------------------------------------
# Styling — dark terminal sidebar + gradient main canvas, matching reference
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');

    html, body, [class*="css"]  {
        font-family: 'JetBrains Mono', monospace;
    }

    /* Main app background — soft blue -> pink -> orange gradient */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 20% 15%, #1b2440 0%, #0d1224 28%, #2a1650 48%, #7a2c6e 68%, #d1497a 85%, #f0894a 100%);
        background-attachment: fixed;
    }
    [data-testid="stHeader"] {
        background: rgba(0,0,0,0);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0a0a12;
        border-right: 1px solid #1f2233;
    }
    [data-testid="stSidebar"] * {
        color: #d7dae0;
    }

    .codude-logo {
        font-size: 1.9rem;
        font-weight: 800;
        color: #f2f2f2;
        letter-spacing: 0.5px;
        margin-bottom: 0;
    }
    .codude-logo span {
        color: #4fd1a5;
    }
    .codude-subtitle {
        color: #7d8190;
        font-size: 0.85rem;
        margin-top: -6px;
        margin-bottom: 22px;
    }
    .sidebar-section-label {
        color: #4fd1a5;
        font-size: 0.72rem;
        letter-spacing: 2px;
        font-weight: 700;
        margin: 18px 0 10px 0;
        text-transform: uppercase;
    }

    /* Orange primary buttons (Create project / Generate) */
    div.stButton > button, .stFormSubmitButton > button {
        background: linear-gradient(90deg, #f7a83b, #f5972c);
        color: #1a1006;
        border: none;
        border-radius: 8px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        padding: 0.6rem 1rem;
        transition: transform 0.08s ease, box-shadow 0.15s ease;
        box-shadow: 0 4px 14px rgba(247, 168, 59, 0.25);
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(247, 168, 59, 0.4);
    }

    /* Previous project pills */
    .prev-project-btn button {
        background: linear-gradient(90deg, #f7a83b, #f5972c) !important;
        color: #1a1006 !important;
        text-align: left !important;
        border-radius: 8px !important;
        width: 100%;
    }

    /* Sidebar text input */
    [data-testid="stSidebar"] input {
        background-color: #14151f !important;
        color: #d7dae0 !important;
        border: 1px solid #2a2d3c !important;
        border-radius: 6px !important;
    }

    hr {
        border-color: #1f2233 !important;
    }

    /* Main heading block */
    .hero-wrap {
        margin-top: 6vh;
        text-align: center;
    }
    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        color: #f5f5f7;
    }
    .hero-title .accent {
        color: #4fd1a5;
    }
    .hero-sub {
        color: #d9d9e3;
        font-size: 1.02rem;
        margin-top: 0.4rem;
        margin-bottom: 2.2rem;
        opacity: 0.85;
    }
    .breadcrumb {
        color: #4fd1a5;
        font-size: 0.85rem;
        margin-bottom: 6px;
        font-weight: 600;
    }

    /* Prompt textarea styled like a terminal card */
    .stTextArea textarea {
        background: rgba(10, 10, 20, 0.55) !important;
        border: 1.5px solid #e8517a !important;
        color: #f2f2f2 !important;
        border-radius: 10px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.95rem !important;
        backdrop-filter: blur(6px);
    }
    .stTextArea textarea::placeholder {
        color: #b9bccb !important;
        opacity: 0.7;
    }

    /* Generate button width */
    .generate-btn {
        width: 100%;
    }
    .generate-btn button {
        width: 100%;
        min-width: 0;
    }

    .stElementContainer[class*="st-key-delete_project"] button[data-testid="stBaseButton-secondary"],
    .stElementContainer[class*="st-key-confirm_delete_"] button[data-testid="stBaseButton-secondary"] {
        background: #e53e3e !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 14px rgba(229, 62, 62, 0.25) !important;
    }
    .stElementContainer[class*="st-key-delete_project"] button[data-testid="stBaseButton-secondary"]:hover,
    .stElementContainer[class*="st-key-confirm_delete_"] button[data-testid="stBaseButton-secondary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(229, 62, 62, 0.35) !important;
    }

    /* Typewriter / file-writing animation panel */
    .terminal-panel {
        background: rgba(6, 8, 16, 0.72);
        border: 1px solid #2a2d3c;
        border-radius: 10px;
        padding: 18px 20px;
        margin-top: 22px;
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
        box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    }
    .terminal-line {
        color: #9ae6b4;
        font-size: 0.9rem;
        margin: 4px 0;
        white-space: pre-wrap;
        word-break: break-all;
    }
    .terminal-line .path {
        color: #f7a83b;
        font-weight: 700;
    }
    .terminal-line .ok {
        color: #4fd1a5;
    }
    .terminal-cursor {
        display: inline-block;
        width: 8px;
        height: 1em;
        background: #9ae6b4;
        margin-left: 2px;
        animation: blink 0.9s steps(1) infinite;
        vertical-align: text-bottom;
    }
    @keyframes blink {
        50% { opacity: 0; }
    }
    .code-preview {
        background: #0a0d16;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 8px 0 16px 0;
        color: #cbd5e1;
        font-size: 0.82rem;
        line-height: 1.45;
        max-height: 220px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="codude-logo">🛠️ COD<span>udE</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="codude-subtitle">your AI pair programmer</div>', unsafe_allow_html=True)

    if st.button("＋ Create project", use_container_width=True):
        st.session_state.current_project = ""
        st.session_state.prompt_text = ""
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="sidebar-section-label">Current project</div>', unsafe_allow_html=True)
    st.session_state.current_project = st.text_input(
        "current_project",
        value=st.session_state.current_project,
        placeholder="e.g. colourful-todo-app",
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown('<div class="sidebar-section-label">Previous projects</div>', unsafe_allow_html=True)
    for i, proj in enumerate(st.session_state.previous_projects):
        st.markdown('<div class="prev-project-btn">', unsafe_allow_html=True)
        if st.button(f"▸ {proj}", key=f"prev_{i}", use_container_width=True):
            st.session_state.current_project = proj
            st.session_state.prompt_text = ""
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main hero
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-wrap">
        <div class="hero-title">&gt; What should <span class="accent">COD</span>udE build?</div>
        <div class="hero-sub">Describe an app in plain English. CODudE plans it, architects the files, and writes the code.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

center = st.container()
with center:
    col_l, col_mid, col_r = st.columns([1, 3, 1])
    with col_mid:
        st.markdown('<div class="breadcrumb">~/CODudE ></div>', unsafe_allow_html=True)
        st.session_state.prompt_text = st.text_area(
            "prompt",
            value=st.session_state.prompt_text,
            placeholder="Build a colourful, modern todo app in HTML, CSS and JS...",
            height=130,
            label_visibility="collapsed",
        )
        st.markdown('<div class="generate-btn">', unsafe_allow_html=True)
        generate_clicked = st.button("Generate ▸", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def get_llm():
    """Return a configured ChatOpenAI client if credentials are available, else None."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="nvidia/nemotron-3-super-120b-a12b:free",
            openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
            openai_api_base="https://openrouter.ai/api/v1",
        )
    except Exception:
        return None


def run_live_pipeline(user_prompt: str, log_area, project_root: str):
    """Try to run the real planner/architect/coder pipeline from agent/. Returns dict of {filepath: content} or raises."""
    from agent.states import Plan, TaskPlan
    from agent.prompts import planner_prompt, architect_prompt, coder_system_prompt
    from agent.tools import write_file, read_file, set_project_root

    llm = get_llm()
    if llm is None:
        raise RuntimeError("No OPENROUTER_API_KEY configured. Please set your API key.")

    set_project_root(project_root)
    os.makedirs(project_root, exist_ok=True)

    type_line(log_area, "→ planning project structure...")
    plan = llm.with_structured_output(Plan).invoke(planner_prompt(user_prompt))

    type_line(log_area, f"→ plan ready: <span class='ok'>{plan.name}</span>")
    type_line(log_area, "→ architecting implementation tasks...")
    task_plan = llm.with_structured_output(TaskPlan).invoke(architect_prompt(plan=plan.model_dump_json()))
    task_plan.plan = plan

    written = {}
    sys_prompt = coder_system_prompt()
    for step in task_plan.implementation_steps:
        type_writing_file(log_area, step.filepath)
        existing = read_file.run(step.filepath)

        # 1. Use .stream() instead of .invoke() for real-time animations
        response_stream = llm.stream(
            [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Task: {step.task_description}\nFile: {step.filepath}\n"
                        f"Existing content:\n{existing}\n"
                        "Return ONLY the full new file content, nothing else."
                    ),
                },
            ]
        )

        content = ""
        # 2. Create a dynamic placeholder in the Streamlit UI
        code_placeholder = log_area.empty()

        # 3. Iterate over the stream and animate the text
        for chunk in response_stream:
            chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
            content += chunk_text
            
            # Limit the display length to prevent UI lag on massive files
            display_snippet = content[:600] + ("\n..." if len(content) > 600 else "")
            code_placeholder.code(display_snippet, line_numbers=False)

        write_file.run({"path": step.filepath, "content": content})
        written[step.filepath] = content
        type_done_file(log_area, step.filepath)

    return written


# ---------------------------------------------------------------------------
# Animation helpers
# ---------------------------------------------------------------------------

def type_line(container, html_text, delay=0.012):
    """Typewriter-render a single status line into the running log."""
    placeholder = container.empty()
    buffer = ""
    plain_len = len(html_text)
    # simple char-by-char reveal for the visible text portion
    for i in range(1, plain_len + 1):
        buffer = html_text[:i]
        placeholder.markdown(f'<div class="terminal-line">{buffer}<span class="terminal-cursor"></span></div>', unsafe_allow_html=True)
        time.sleep(delay)
    placeholder.markdown(f'<div class="terminal-line">{html_text}</div>', unsafe_allow_html=True)


def type_writing_file(container, filepath):
    dots_frames = ["", ".", "..", "..."]
    placeholder = container.empty()
    for _ in range(2):
        for d in dots_frames:
            placeholder.markdown(
                f'<div class="terminal-line">✍️  writing <span class="path">{filepath}</span>{d}</div>',
                unsafe_allow_html=True,
            )
            time.sleep(0.09)
    st.session_state[f"placeholder_done_{filepath}"] = placeholder


def type_done_file(container, filepath):
    placeholder = st.session_state.get(f"placeholder_done_{filepath}")
    text = f'<div class="terminal-line">✅ <span class="ok">wrote</span> <span class="path">{filepath}</span></div>'
    if placeholder is not None:
        placeholder.markdown(text, unsafe_allow_html=True)
    else:
        container.markdown(text, unsafe_allow_html=True)


def list_project_files(project_name: str) -> list[Path]:
    project_root = Path(get_project_root_from_name(project_name))
    if not project_root.exists():
        return []
    return sorted([p for p in project_root.rglob("*") if p.is_file()])


def build_project_zip(project_name: str) -> bytes:
    project_root = Path(get_project_root_from_name(project_name))
    if not project_root.exists():
        return b""

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(project_root.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(project_root).as_posix())
    return zip_buffer.getvalue()


def render_project_file_list(project_name: str):
    files = list_project_files(project_name)
    if not files:
        st.info("No generated files found for this project yet.")
        return

    zip_bytes = build_project_zip(project_name)
    st.download_button(
        label="Download project to computer",
        data=zip_bytes,
        file_name=f"{slugify_project(project_name)}.zip",
        mime="application/zip",
        use_container_width=True,
        disabled=not zip_bytes,
    )

    delete_button_key = f"delete_project_{slugify_project(project_name)}"
    st.markdown('<div class="delete-project-btn">', unsafe_allow_html=True)
    if st.button(f"Delete project", key=delete_button_key, use_container_width=True):
        st.session_state.delete_pending = project_name
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.delete_pending == project_name:
        st.warning(f"Are you sure you want to delete the project '{project_name}'? This will remove all files and the project entry.")
        confirm_col, cancel_col = st.columns([1, 1])
        with confirm_col:
            st.markdown('<div class="delete-project-btn">', unsafe_allow_html=True)
            if st.button("Confirm delete", key=f"confirm_delete_{delete_button_key}", use_container_width=True):
                delete_project_files(project_name)
                remove_project_from_registry(project_name)
                if project_name in st.session_state.previous_projects:
                    st.session_state.previous_projects.remove(project_name)
                st.session_state.current_project = ""
                st.session_state.prompt_text = ""
                st.session_state.delete_pending = ""
                return
            st.markdown('</div>', unsafe_allow_html=True)
        with cancel_col:
            if st.button("Cancel", key=f"cancel_delete_{delete_button_key}"):
                st.session_state.delete_pending = ""
                return

    st.markdown(f"### Generated files for **{project_name}**")
    for file_path in files:
        relative_path = file_path.relative_to(Path(get_project_root_from_name(project_name))).as_posix()
        with st.expander(relative_path, expanded=False):
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                st.error(f"Unable to read {relative_path}: {exc}")
                continue
            lang = "javascript" if file_path.suffix == ".js" else "css" if file_path.suffix == ".css" else "html" if file_path.suffix == ".html" else "text"
            st.code(content, language=lang)


# ---------------------------------------------------------------------------
# Generate action
# ---------------------------------------------------------------------------
if generate_clicked:
    prompt = st.session_state.prompt_text.strip()
    if not prompt:
        st.warning("Describe what CODudE should build first.")
    else:
        project_name = st.session_state.current_project.strip() or "-".join(prompt.lower().split()[:3])
        with center:
            with col_mid:
                st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
                log_area = st.container()
                type_line(log_area, f"→ initializing project <span class='path'>{project_name}</span>")

                written_files = None
                project_root = get_project_root_from_name(project_name)
                
                # We attempt to run the pipeline. If it fails, it will now halt and error honestly 
                # rather than writing a dummy snake or tic-tac-toe game.
                try:
                    written_files = run_live_pipeline(prompt, log_area, project_root)
                    type_line(log_area, f"→ <span class='ok'>done.</span> {len(written_files)} file(s) written.")
                    
                    save_project_registry(project_name, prompt)

                    if project_name not in st.session_state.previous_projects:
                        st.session_state.previous_projects.insert(0, project_name)
                    st.session_state.current_project = project_name
                except Exception as e:
                    error_msg = f"→ Pipeline failed: {str(e)}"
                    type_line(log_area, f"<span style='color:#e53e3e'>{error_msg}</span>")
                    st.error(error_msg)
                    st.stop()
                    
                st.markdown("</div>", unsafe_allow_html=True)

        if written_files:
            render_project_file_list(project_name)
else:
    if st.session_state.current_project:
        render_project_file_list(st.session_state.current_project)