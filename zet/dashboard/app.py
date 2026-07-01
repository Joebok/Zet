from dataclasses import asdict
from datetime import datetime
import html
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import streamlit.components.v1 as components

from zet.app import ZetApp
from zet.services.config_service import ConfigService, ConfigServiceError
from zet.services.prompt_review_service import LocalRenderUnavailable, PromptReviewService, is_prompt_review_asset

SCRIPTS_PATH = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from Template_Section_Editor import load_bundles, load_editor_sections, list_pipeline_names, save_template_sections


def format_value(value):
    return "None" if value is None else value


def format_timestamp_with_age(value):
    if value is None:
        return "None"
    text = str(value).strip()
    if not text:
        return "None"
    try:
        stamp = datetime.fromisoformat(text)
        now = datetime.now(stamp.tzinfo) if stamp.tzinfo else datetime.now()
        delta = now - stamp
        total_seconds = max(0, int(delta.total_seconds()))
        if total_seconds < 60:
            age_text = "just now"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            age_text = f"{minutes} min ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            age_text = f"{hours}h {minutes}m ago" if minutes else f"{hours}h ago"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            age_text = f"{days}d {hours}h ago" if hours else f"{days}d ago"
        return f"{text} ({age_text})"
    except Exception:
        return text


def discover_characters(base_character_path: str) -> list[str]:
    root = Path(base_character_path)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def discover_phases(base_character_path: str, character: str) -> list[str]:
    root = Path(base_character_path) / character
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def asset_to_row(asset) -> dict:
    stage_url = f"?page=Assets&selected_asset={asset.asset_id}&stage={asset.pipeline_stage}"
    if is_prompt_review_asset(asset):
        stage_url = f"?page=Prompt%20Review&selected_asset={asset.asset_id}&review_asset={asset.asset_id}&stage={asset.pipeline_stage}"
    return {
        "asset_id": asset.asset_id,
        "pipeline": asset.pipeline,
        "body_view": asset.body_view,
        "head_view": format_value(asset.head_view),
        "costume": format_value(asset.costume),
        "expression": format_value(asset.expression),
        "asset_state": asset.asset_state,
        "pipeline_stage": stage_url,
        "actor": asset.actor,
        "ai_state": format_value(asset.ai_state),
        "final_image_output": format_value(asset.final_image_output),
        "updated_at": format_timestamp_with_age(asset.updated_at),
    }


def selected_asset_id_from_event(selection_event, asset_rows: list[dict]) -> int | None:
    if selection_event is None:
        return None
    selection = getattr(selection_event, "selection", None)
    if selection is None:
        return None
    rows = selection.get("rows", [])
    if not rows:
        return None
    row_index = rows[0]
    if row_index < 0 or row_index >= len(asset_rows):
        return None
    return asset_rows[row_index]["asset_id"]


def selection_state_key(character: str, phase: str) -> str:
    return f"selected_asset_id::{character}::{phase}"


def prompt_review_state_key(character: str, phase: str) -> str:
    return f"prompt_review_asset_id::{character}::{phase}"


def dashboard_page_state_key(character: str, phase: str) -> str:
    return f"dashboard_page::{character}::{phase}"


def pending_dashboard_page_state_key(character: str, phase: str) -> str:
    return f"pending_dashboard_page::{character}::{phase}"


def handled_review_query_state_key(character: str, phase: str) -> str:
    return f"handled_review_query::{character}::{phase}"


def store_action_message(level: str, message: str) -> None:
    st.session_state["zet_action_message"] = {"level": level, "message": message}


def show_action_message() -> None:
    payload = st.session_state.pop("zet_action_message", None)
    if not payload:
        return
    level = payload["level"]
    message = payload["message"]
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)


def action_disabled_reason(asset_ref) -> dict[str, str | None]:
    asset = asset_ref.get()
    reasons = {
        "move_next": None,
        "stage_ai_ask": None,
        "run_current_worker": None,
        "run_housekeeping": None,
        "retry_ai": None,
        "regenerate": None,
        "promote_to_locked": None,
    }
    if asset.actor != "AI_AGENT":
        reasons["stage_ai_ask"] = "AI ask staging is only available when Actor is AI_AGENT."
    if asset.actor != "PYTHON":
        reasons["run_current_worker"] = "Current worker can only run when Actor is PYTHON."
    if asset.actor != "AI_AGENT":
        reasons["retry_ai"] = "Retry AI is only available when Actor is AI_AGENT."
    if not asset_ref.candidate_image_path().exists():
        reasons["promote_to_locked"] = "Promote to LOCKED requires an existing candidate image."
    return reasons


def path_row(label: str, path: Path) -> dict:
    return {
        "Path": label,
        "Value": str(path),
        "Exists": "yes" if path.exists() else "no",
    }


def load_text_if_exists(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def prompt_review_service_for_app(app: ZetApp) -> PromptReviewService:
    service = getattr(app, "prompt_review_service", None)
    if service is None:
        service = PromptReviewService(app.asset_repository, app.asset_service, app.path_service)
        app.prompt_review_service = service
    return service


def search_terms_from_query(query: str) -> list[str]:
    return [term.strip() for term in query.split(",") if term.strip()]


def highlighted_prompt_html(prompt_text: str, search_terms: list[str]) -> tuple[str, int]:
    if not search_terms:
        return html.escape(prompt_text), 0

    pattern = re.compile("|".join(re.escape(term) for term in search_terms), re.IGNORECASE)
    count = 0
    pieces: list[str] = []
    cursor = 0
    for match in pattern.finditer(prompt_text):
        count += 1
        pieces.append(html.escape(prompt_text[cursor:match.start()]))
        pieces.append(f"<mark>{html.escape(match.group(0))}</mark>")
        cursor = match.end()
    pieces.append(html.escape(prompt_text[cursor:]))
    return "".join(pieces), count


def show_copyable_prompt(prompt_text: str, search_query: str = "") -> None:
    prompt_json = json.dumps(prompt_text)
    search_terms = search_terms_from_query(search_query)
    prompt_html, match_count = highlighted_prompt_html(prompt_text, search_terms)
    if search_query.strip():
        if match_count:
            st.caption(f"{match_count} match(es) for: {', '.join(search_terms)}")
        else:
            st.warning(f"No matches for: {', '.join(search_terms)}")
    components.html(
        f"""
        <style>
        body {{
            margin: 0;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .prompt-shell {{
            position: relative;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 0.35rem;
            color: #111827;
            height: 720px;
            overflow: auto;
            padding: 2.6rem 1rem 1rem 1rem;
            box-sizing: border-box;
        }}
        .copy-link {{
            position: sticky;
            top: 0;
            float: right;
            margin-top: -1.8rem;
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 0.25rem;
            color: #2563eb;
            cursor: pointer;
            font-size: 0.82rem;
            line-height: 1;
            padding: 0.35rem 0.55rem;
            z-index: 2;
        }}
        .copy-link:hover {{
            background: #eff6ff;
        }}
        pre {{
            color: #111827;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.98rem;
            line-height: 1.55;
            margin: 0;
            white-space: pre-wrap;
            word-break: normal;
        }}
        mark {{
            background: #fde68a;
            color: #111827;
            border-radius: 0.15rem;
            padding: 0.02rem 0.08rem;
        }}
        </style>
        <div class="prompt-shell">
          <button class="copy-link" type="button" onclick="copyPrompt()">copy</button>
          <pre>{prompt_html}</pre>
        </div>
        <script>
        const promptText = {prompt_json};
        async function copyPrompt() {{
            const button = document.querySelector('.copy-link');
            try {{
                await navigator.clipboard.writeText(promptText);
                button.textContent = 'copied';
                setTimeout(() => button.textContent = 'copy', 1400);
            }} catch (error) {{
                button.textContent = 'copy failed';
                setTimeout(() => button.textContent = 'copy', 1800);
            }}
        }}
        </script>
        """,
        height=735,
        scrolling=False,
    )


def show_prompt_review(app: ZetApp, character: str, phase: str, asset_id: int | None) -> None:
    st.subheader("Prompt Review")
    if asset_id is None:
        st.info("Select a PROMPT_REVIEW asset from the Assets tab.")
        return

    try:
        prompt_review_service = prompt_review_service_for_app(app)
        context = prompt_review_service.get_context(character, phase, asset_id)
        asset = context.asset
    except Exception as exc:
        st.error(str(exc))
        return

    st.markdown(
        f'<div class="zet-selected-bar">asset_id: {asset.asset_id} | {asset.pipeline} | '
        f'{asset.body_view} | {asset.pipeline_stage} | {asset.actor}</div>',
        unsafe_allow_html=True,
    )

    if not is_prompt_review_asset(asset):
        st.warning("This asset is not currently at PROMPT_REVIEW / HUMAN_AGENT.")
        return

    prompt_path = context.prompt_path
    if prompt_path is None:
        st.error("No prompt file was found for this asset.")
        st.table([path_row("Candidate", path) for path in context.prompt_candidates])
        return

    st.caption(str(prompt_path))
    prompt_text = context.prompt_text or ""

    prompt_col, review_col = st.columns([1.35, 0.85], gap="large")
    with prompt_col:
        search_query = st.text_input(
            "Search prompt",
            placeholder="Search terms, comma-separated",
            key=f"prompt_search::{character}::{phase}::{asset.asset_id}",
        )
        show_copyable_prompt(prompt_text, search_query)

    with review_col:
        if asset.pipeline == "Body-Reference":
            if st.button("Generate Local Test Image", use_container_width=True):
                try:
                    with st.spinner("Generating local test image with ComfyUI..."):
                        result = prompt_review_service.generate_local_test_render(character, phase, asset.asset_id)
                    store_action_message("success", f"Local test image generated: {result.image_path}")
                    st.rerun()
                except LocalRenderUnavailable:
                    st.error("Local render backend unavailable.")
                except Exception as exc:
                    st.error(str(exc))

            latest_render = context.latest_local_test_render
            if latest_render:
                st.image(str(latest_render), caption="Latest local test render", use_container_width=True)
            else:
                st.info("No local test render yet.")

        approve_clicked = st.button("Approve", type="primary", use_container_width=True)
        fail_clicked = st.button("Fail", use_container_width=True)

    try:
        if approve_clicked:
            updated_asset = prompt_review_service.approve(character, phase, asset.asset_id)
            st.session_state[selection_state_key(character, phase)] = updated_asset.asset_id
            st.session_state[pending_dashboard_page_state_key(character, phase)] = "Assets"
            st.query_params["page"] = "Assets"
            st.query_params.pop("review_asset", None)
            store_action_message("success", f"Prompt approved. Asset {updated_asset.asset_id} moved to {updated_asset.pipeline_stage}.")
            st.rerun()
        if fail_clicked:
            updated_asset = prompt_review_service.fail(character, phase, asset.asset_id)
            st.session_state[selection_state_key(character, phase)] = updated_asset.asset_id
            st.session_state[pending_dashboard_page_state_key(character, phase)] = "Assets"
            st.query_params["page"] = "Assets"
            st.query_params.pop("review_asset", None)
            store_action_message("error", f"Prompt failed. Asset {updated_asset.asset_id} moved to {updated_asset.pipeline_stage}.")
            st.rerun()
    except Exception as exc:
        store_action_message("error", str(exc))
        st.rerun()


def monitor_row(result) -> dict:
    return {
        "worker_id": result.worker_id,
        "host": result.host,
        "status": result.status,
        "ollama_ok": "yes" if result.ollama_ok else "no",
        "responded_at": format_timestamp_with_age(result.responded_at),
        "models": ", ".join(result.models) if result.models else "",
        "message": format_value(result.message),
    }


def request_row(request_dir: Path) -> dict:
    payload = {}
    request_path = request_dir / "request.json"
    if request_path.exists():
        try:
            import json

            payload = json.loads(request_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    return {
        "test_id": request_dir.name,
        "created_at": format_timestamp_with_age(payload.get("created_at")),
        "instruction": format_value(payload.get("instruction")),
        "path": str(request_dir),
    }


def load_view_options() -> dict:
    path = PROJECT_ROOT / "Config" / "Prompt_View_Text.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("views", data)


def template_path_for_selection(base_character_path: str, character: str, phase: str) -> Path:
    return Path(base_character_path) / character / phase / "Character_Image_Template.md"


def show_template_editor(config, character: str, phase: str) -> None:
    st.subheader("Template Section Editor")
    pipelines = list_pipeline_names(PROJECT_ROOT)
    if not pipelines:
        st.info("No prompt task bundles are configured.")
        return

    editor_col_1, editor_col_2 = st.columns([1, 1])
    with editor_col_1:
        pipeline = st.selectbox("Pipeline", pipelines, index=pipelines.index("body-reference") if "body-reference" in pipelines else 0)

    bundles = load_bundles(PROJECT_ROOT)
    bundle = bundles.get(pipeline, {})
    needs_view = any("{VIEW}" in name for name in list(bundle.get("required_sections", [])) + list(bundle.get("optional_sections", [])))
    views = load_view_options()
    view_token = next(iter(views.keys()), "")
    if needs_view:
        labels = {token: f"{token} - {value.get('label', token)}" for token, value in views.items()}
        with editor_col_2:
            view_token = st.selectbox("View", list(labels.keys()), format_func=lambda token: labels[token])

    template_path = template_path_for_selection(config.base_character_path, character, phase)
    st.caption(str(template_path))

    try:
        sections = load_editor_sections(template_path, pipeline, view_token, PROJECT_ROOT)
    except Exception as exc:
        st.error(str(exc))
        return

    with st.form(f"template-editor-{character}-{phase}-{pipeline}-{view_token}"):
        updated_sections = {}
        section_order = []
        for section in sections:
            section_order.append(section.name)
            badge = "required" if section.required else "optional"
            st.markdown(f"**{section.label}** `{section.name}` `{badge}`")
            if section.description:
                st.caption(section.description)
            updated_sections[section.name] = st.text_area(
                section.name,
                value=section.text,
                height=180,
                label_visibility="collapsed",
            )
        save_clicked = st.form_submit_button("Save Sections", use_container_width=True)

    if save_clicked:
        try:
            save_template_sections(template_path, updated_sections, section_order)
            store_action_message("success", f"Saved {len(updated_sections)} section(s) to {template_path}.")
            st.rerun()
        except Exception as exc:
            store_action_message("error", str(exc))
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Zet Dashboard", layout="wide")
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.6rem;
            padding-bottom: 0.8rem;
        }
        .zet-title {
            font-family: "Brush Script MT", "Lucida Handwriting", cursive;
            font-size: 3rem;
            line-height: 1;
            margin: 0 0 0.2rem 0;
        }
        .zet-selected-bar {
            background: #f3f4f6;
            border: 1px solid #d1d5db;
            border-radius: 0.5rem;
            color: #374151;
            padding: 0.45rem 0.7rem;
            margin: 0.15rem 0 0.45rem 0;
        }
        .zet-prompt-viewer {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 0.35rem;
            color: #111827;
            max-height: 68vh;
            overflow: auto;
            padding: 1rem;
        }
        .zet-prompt-viewer pre {
            color: #111827;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.98rem;
            line-height: 1.55;
            margin: 0;
            white-space: pre-wrap;
            word-break: normal;
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
            gap: 0.45rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem;
        }
        div[data-testid="stSelectbox"] {
            margin-bottom: 0;
        }
        div[data-testid="stButton"] {
            margin-top: 0;
        }
        div[data-testid="stDataFrame"] {
            margin-top: -0.25rem;
        }
        h3 {
            margin-top: 0.35rem;
            margin-bottom: 0.25rem;
        }
        p {
            margin-bottom: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="zet-title">ZET</div>', unsafe_allow_html=True)
    show_action_message()
    config_path = "config.toml"

    try:
        config = ConfigService.load(config_path)
        app = ZetApp.from_config(config_path)
    except ConfigServiceError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Unable to load app from config: {exc}")
        return

    characters = discover_characters(config.base_character_path)
    if not characters:
        st.info("No characters found under the configured BaseCharacterPath.")
        return

    control_col_1, control_col_2 = st.columns([1, 1])

    with control_col_1:
        character = st.selectbox("Character", characters)

    phases = discover_phases(config.base_character_path, character)
    if not phases:
        st.info(f"No phases found for character {character}.")
        return

    with control_col_2:
        phase = st.selectbox("Phase", phases)

    state_key = selection_state_key(character, phase)
    review_key = prompt_review_state_key(character, phase)
    page_key = dashboard_page_state_key(character, phase)
    pending_page_key = pending_dashboard_page_state_key(character, phase)
    handled_review_key = handled_review_query_state_key(character, phase)
    page_options = ["Assets", "Prompt Review", "Template Editor", "AI Controls"]
    pending_page = st.session_state.pop(pending_page_key, None)
    if pending_page in page_options:
        st.session_state[page_key] = pending_page
    query_page = st.query_params.get("page")
    if query_page in page_options and page_key not in st.session_state:
        st.session_state[page_key] = query_page
    query_selected_asset = st.query_params.get("selected_asset")
    if query_selected_asset:
        try:
            st.session_state[state_key] = int(query_selected_asset)
        except ValueError:
            st.query_params.pop("selected_asset", None)
    query_review_asset = st.query_params.get("review_asset")
    if query_review_asset:
        try:
            review_asset_id = int(query_review_asset)
            st.session_state[state_key] = review_asset_id
            st.session_state[review_key] = review_asset_id
            if st.session_state.get(handled_review_key) != query_review_asset:
                st.session_state[page_key] = "Prompt Review"
                st.session_state[handled_review_key] = query_review_asset
        except ValueError:
            st.query_params.pop("review_asset", None)

    try:
        assets = app.list_assets(character, phase)
    except Exception as exc:
        st.error(str(exc))
        return

    if not assets:
        st.info(f"No assets found for {character}/{phase}.")
        show_template_editor(config, character, phase)
        return

    if st.session_state.get(page_key) not in page_options:
        st.session_state[page_key] = "Assets"

    active_page = st.segmented_control(
        "Dashboard section",
        page_options,
        key=page_key,
        label_visibility="collapsed",
    )
    st.query_params["page"] = active_page
    if active_page != "Prompt Review":
        st.query_params.pop("review_asset", None)

    if active_page == "Assets":
        st.subheader("Assets")
        asset_rows = [asset_to_row(asset) for asset in assets]
        selection_event = st.dataframe(
            asset_rows,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "pipeline_stage": st.column_config.LinkColumn(
                    "pipeline_stage",
                    help="PROMPT_REVIEW links open the prompt review panel.",
                    display_text=r"stage=([^&]+)",
                )
            },
            column_order=[
                "asset_id",
                "pipeline",
                "body_view",
                "head_view",
                "costume",
                "expression",
                "asset_state",
                "pipeline_stage",
                "actor",
                "ai_state",
                "final_image_output",
                "updated_at",
            ],
        )

        selected_asset_id = selected_asset_id_from_event(selection_event, asset_rows)
        if selected_asset_id is not None:
            st.session_state[state_key] = selected_asset_id
        else:
            selected_asset_id = st.session_state.get(state_key)

        valid_asset_ids = {asset.asset_id for asset in assets}
        if selected_asset_id not in valid_asset_ids:
            selected_asset_id = assets[0].asset_id
            st.session_state[state_key] = selected_asset_id
            st.info("Click a row in the asset table to switch the detail view. Showing the first asset by default.")

        try:
            asset_ref = app.asset(character, phase, selected_asset_id)
            asset = asset_ref.get()
        except Exception as exc:
            st.error(str(exc))
            return

        summary_items = [
            f"asset_id: {asset.asset_id}",
            f"{asset.pipeline}",
            f"{asset.body_view}",
            f"{asset.pipeline_stage}",
            f"{asset.actor}",
            f"ai_state: {format_value(asset.ai_state)}",
        ]
        st.markdown(
            f'<div class="zet-selected-bar">{" | ".join(summary_items)}</div>',
            unsafe_allow_html=True,
        )
        if is_prompt_review_asset(asset):
            if st.button("Open Prompt Review", use_container_width=True):
                st.session_state[review_key] = asset.asset_id
                st.session_state[pending_page_key] = "Prompt Review"
                st.query_params["page"] = "Prompt Review"
                st.query_params["review_asset"] = str(asset.asset_id)
                st.rerun()

        disabled_reasons = action_disabled_reason(asset_ref)
        action_columns = st.columns(7)

        with action_columns[0]:
            stage_ai_ask_clicked = st.button(
                "Stage AI Ask",
                use_container_width=True,
                disabled=disabled_reasons["stage_ai_ask"] is not None,
            )
        with action_columns[1]:
            run_worker_clicked = st.button(
                "Run Current Worker",
                use_container_width=True,
                disabled=disabled_reasons["run_current_worker"] is not None,
            )
        with action_columns[2]:
            move_next_clicked = st.button("Move Next", use_container_width=True)
        with action_columns[3]:
            run_housekeeping_clicked = st.button("Run Housekeeping", use_container_width=True)
        with action_columns[4]:
            retry_ai_clicked = st.button(
                "Retry AI",
                use_container_width=True,
                disabled=disabled_reasons["retry_ai"] is not None,
            )
        with action_columns[5]:
            regenerate_clicked = st.button("Regenerate", use_container_width=True)
        with action_columns[6]:
            promote_clicked = st.button(
                "Promote to LOCKED",
                use_container_width=True,
                disabled=disabled_reasons["promote_to_locked"] is not None,
            )

        if disabled_reasons["stage_ai_ask"]:
            st.caption(disabled_reasons["stage_ai_ask"])
        if disabled_reasons["run_current_worker"]:
            st.caption(disabled_reasons["run_current_worker"])
        if disabled_reasons["retry_ai"]:
            st.caption(disabled_reasons["retry_ai"])
        if disabled_reasons["promote_to_locked"]:
            st.caption(disabled_reasons["promote_to_locked"])

        try:
            if stage_ai_ask_clicked:
                ask_path = asset_ref.stage_ai_ask()
                st.session_state[state_key] = selected_asset_id
                store_action_message("success", f"AI ask staged for Asset {selected_asset_id} at {ask_path}.")
                st.rerun()
            if run_worker_clicked:
                updated_asset = asset_ref.run_current_worker()
                worker_name = app.asset_service.worker_service.last_worker_module_name or "unknown"
                st.session_state[state_key] = updated_asset.asset_id
                store_action_message(
                    "success",
                    f"Worker {worker_name} executed for Asset {updated_asset.asset_id}.",
                )
                st.rerun()
            if move_next_clicked:
                updated_asset = asset_ref.move_next()
                st.session_state[state_key] = updated_asset.asset_id
                store_action_message("success", f"Asset {updated_asset.asset_id} moved to {updated_asset.pipeline_stage}.")
                st.rerun()
            if run_housekeeping_clicked:
                pipeline_path = asset_ref.run_housekeeping()
                st.session_state[state_key] = selected_asset_id
                store_action_message("success", f"Housekeeping complete for Asset {selected_asset_id} at {pipeline_path}.")
                st.rerun()
            if retry_ai_clicked:
                updated_asset = asset_ref.retry_ai()
                st.session_state[state_key] = updated_asset.asset_id
                store_action_message("success", f"AI retry requested for Asset {updated_asset.asset_id}.")
                st.rerun()
            if regenerate_clicked:
                updated_asset = asset_ref.regenerate()
                st.session_state[state_key] = updated_asset.asset_id
                store_action_message("success", f"Asset {updated_asset.asset_id} reset to {updated_asset.pipeline_stage}.")
                st.rerun()
            if promote_clicked:
                updated_asset = asset_ref.promote_to_locked()
                st.session_state[state_key] = updated_asset.asset_id
                store_action_message("success", f"Asset {updated_asset.asset_id} promoted to LOCKED.")
                st.rerun()
        except Exception as exc:
            store_action_message("error", str(exc))
            st.rerun()

        asset = asset_ref.get()
        character_path = app.path_service.character_path(character, phase)
        character_asset_path = app.path_service.character_asset_path(character, phase)
        pipeline_path = asset_ref.pipeline_path()
        candidate_image_path = asset_ref.candidate_image_path()
        locked_image_path = asset_ref.locked_image_path()
        stage_path = pipeline_path / "_stage.txt"
        history_path = pipeline_path / "_history.log"

        st.subheader("Images")
        candidate_col, locked_col = st.columns(2)

        with candidate_col:
            if candidate_image_path.exists():
                st.image(str(candidate_image_path), caption="Candidate", use_container_width=True)
            else:
                st.info("No candidate image found.")

        with locked_col:
            if locked_image_path.exists():
                st.image(str(locked_image_path), caption="Locked", use_container_width=True)
            else:
                st.info("No locked image found.")

        details_col, files_col = st.columns([1, 1])

        with details_col:
            st.subheader("Asset Details")
            st.json({key: format_value(value) for key, value in asdict(asset).items()})

            st.subheader("Derived Paths")
            st.table(
                [
                    path_row("CharacterPath", character_path),
                    path_row("CharacterAssetPath", character_asset_path),
                    path_row("PipelinePath", pipeline_path),
                    path_row("CandidateImagePath", candidate_image_path),
                    path_row("LockedImagePath", locked_image_path),
                ]
            )

        with files_col:
            st.subheader("Housekeeping Files")

            stage_contents = load_text_if_exists(stage_path)
            if stage_contents is None:
                st.info("No stage marker found.")
            else:
                st.markdown("**Stage Marker**")
                st.text(stage_contents)

            history_contents = load_text_if_exists(history_path)
            if history_contents is None:
                st.info("No history log found.")
            else:
                st.markdown("**History Log**")
                st.text(history_contents)

    if active_page == "Prompt Review":
        review_asset_id = st.session_state.get(review_key) or st.session_state.get(state_key)
        show_prompt_review(app, character, phase, review_asset_id)

    if active_page == "Template Editor":
        show_template_editor(config, character, phase)

    if active_page == "AI Controls":
        ai_control_col_1, ai_control_col_2, ai_control_col_3, ai_control_col_4, ai_control_col_5 = st.columns([1, 1, 1, 1, 1.5])
        with ai_control_col_1:
            harvest_clicked = st.button("Harvest AI Answers", use_container_width=True)
        with ai_control_col_2:
            stop_clicked = st.button("Stop Proxy", use_container_width=True)
        with ai_control_col_3:
            resume_clicked = st.button("Resume Proxy", use_container_width=True)
        with ai_control_col_4:
            monitor_clicked = st.button("Send Monitor Test", use_container_width=True)
        with ai_control_col_5:
            monitor_instruction = st.text_input(label = "", label_visibility="collapsed", placeholder="Optional note for workers")

        try:
            if harvest_clicked:
                results = app.harvest_ai_answers()
                if results:
                    store_action_message("success", f"Harvested {len(results)} AI answer folder(s).")
                else:
                    store_action_message("info", "No AI answer folders found.")
                st.rerun()
            if monitor_clicked:
                request_path = app.issue_monitor_test(monitor_instruction)
                store_action_message("success", f"Monitor test sent: {request_path.name}")
                st.rerun()
            if stop_clicked:
                stop_state = app.activate_proxy_stop()
                store_action_message(
                    "success",
                    f"Proxy stop activated. Cleared {stop_state['cleared_asks']} ask folder(s).",
                )
                st.rerun()
            if resume_clicked:
                app.resume_proxy_stop()
                store_action_message("success", "Proxy stop cleared. New asks may be processed.")
                st.rerun()
        except Exception as exc:
            store_action_message("error", str(exc))
            st.rerun()

        stop_state = app.proxy_stop_state()
        if stop_state["active"]:
            st.warning(
                "Proxy is STOPPED. New or late-arriving asks from before "
                f"{format_value(stop_state['reject_before_compact'])} will be rejected."
            )
        else:
            st.info("Proxy is ACTIVE.")

        queue_snapshot = app.queue_snapshot()
        monitor_results = app.list_monitor_responses()
        monitor_request_root = app.ai_proxy_service.ai_proxy_path_service.monitor_requests_root()
        request_rows = []
        if monitor_request_root.exists():
            request_rows = [request_row(path) for path in sorted(monitor_request_root.iterdir(), reverse=True) if path.is_dir()]

        queue_col_1, queue_col_2 = st.columns(2)
        with queue_col_1:
            st.subheader("Queue")
            st.markdown(
                f"Ask: {len(queue_snapshot['ask'])} | Claimed: {len(queue_snapshot['claimed'])} | "
                f"Answer: {len(queue_snapshot['answer'])} | Failed: {len(queue_snapshot['failed'])}"
            )
            st.markdown("**Ask**")
            if queue_snapshot["ask"]:
                st.dataframe(queue_snapshot["ask"], use_container_width=True, hide_index=True)
            else:
                st.info("No ask folders waiting.")
            st.markdown("**Claimed**")
            if queue_snapshot["claimed"]:
                st.dataframe(queue_snapshot["claimed"], use_container_width=True, hide_index=True)
            else:
                st.info("No claimed folders in progress.")

        with queue_col_2:
            st.subheader("Queue Results")
            st.markdown("**Answer**")
            if queue_snapshot["answer"]:
                st.dataframe(queue_snapshot["answer"], use_container_width=True, hide_index=True)
            else:
                st.info("No answer folders yet.")
            st.markdown("**Failed**")
            if queue_snapshot["failed"]:
                st.dataframe(queue_snapshot["failed"], use_container_width=True, hide_index=True)
            else:
                st.info("No failed folders.")

        test_col_1, test_col_2 = st.columns(2)
        with test_col_1:
            st.subheader("Monitor Tests")
            if request_rows:
                st.dataframe(request_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No monitor tests have been sent yet.")

        with test_col_2:
            st.subheader("Monitor Responses")
            if monitor_results:
                st.dataframe(
                    [monitor_row(result) for result in monitor_results],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No worker monitor responses yet.")


if __name__ == "__main__":
    main()
