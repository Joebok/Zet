from dataclasses import asdict
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from zet.app import ZetApp
from zet.services.config_service import ConfigService, ConfigServiceError


def format_value(value):
    return "None" if value is None else value


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
    return {
        "asset_id": asset.asset_id,
        "pipeline": asset.pipeline,
        "body_view": asset.body_view,
        "head_view": format_value(asset.head_view),
        "costume": format_value(asset.costume),
        "expression": format_value(asset.expression),
        "asset_state": asset.asset_state,
        "pipeline_stage": asset.pipeline_stage,
        "actor": asset.actor,
        "ai_state": format_value(asset.ai_state),
        "final_image_output": format_value(asset.final_image_output),
        "updated_at": format_value(asset.updated_at),
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
        "run_housekeeping": None,
        "retry_ai": None,
        "regenerate": None,
        "promote_to_locked": None,
    }
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


def main() -> None:
    st.set_page_config(page_title="Zet Dashboard", layout="wide")
    st.title("Zet Dashboard")
    show_action_message()

    with st.sidebar:
        st.header("Controls")
        config_path = st.text_input("Config path", value="config.toml")

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

    with st.sidebar:
        character = st.selectbox("Character", characters)

    phases = discover_phases(config.base_character_path, character)
    if not phases:
        st.info(f"No phases found for character {character}.")
        return

    with st.sidebar:
        phase = st.selectbox("Phase", phases)

    try:
        assets = app.list_assets(character, phase)
    except Exception as exc:
        st.error(str(exc))
        return

    if not assets:
        st.info(f"No assets found for {character}/{phase}.")
        return

    st.subheader("Assets")
    asset_rows = [asset_to_row(asset) for asset in assets]
    selection_event = st.dataframe(
        asset_rows,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_asset_id = selected_asset_id_from_event(selection_event, asset_rows)
    state_key = selection_state_key(character, phase)
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

    st.subheader("Selected Asset Actions")
    disabled_reasons = action_disabled_reason(asset_ref)
    action_columns = st.columns(5)

    with action_columns[0]:
        move_next_clicked = st.button("Move Next", use_container_width=True)
    with action_columns[1]:
        run_housekeeping_clicked = st.button("Run Housekeeping", use_container_width=True)
    with action_columns[2]:
        retry_ai_clicked = st.button(
            "Retry AI",
            use_container_width=True,
            disabled=disabled_reasons["retry_ai"] is not None,
        )
    with action_columns[3]:
        regenerate_clicked = st.button("Regenerate", use_container_width=True)
    with action_columns[4]:
        promote_clicked = st.button(
            "Promote to LOCKED",
            use_container_width=True,
            disabled=disabled_reasons["promote_to_locked"] is not None,
        )

    if disabled_reasons["retry_ai"]:
        st.caption(disabled_reasons["retry_ai"])
    if disabled_reasons["promote_to_locked"]:
        st.caption(disabled_reasons["promote_to_locked"])

    try:
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


if __name__ == "__main__":
    main()
