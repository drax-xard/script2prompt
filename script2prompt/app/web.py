"""Web wizard: upload -> mode picker -> review/manifest -> generate/export.

Streamlit is an optional ``web`` extra, imported lazily so the core works
without it. Install with ``.venv/bin/pip install .[web]`` then run
``.venv/bin/streamlit run script2prompt/app/web.py``.
"""
from __future__ import annotations

MODE_HELP = {
    "T2VA": "Text to video+audio. No references needed; no instruction line.",
    "I2VA": "Text + first frame. Reference: 1 image. Fixed first-frame instruction.",
    "FL2VA": "Text + first and last frames. References: 2 images; single shot.",
    "L2VA": "Text + last frame. Reference: 1 image; converges on the frame.",
    "R2V": "Full reference. References: subject images + voice samples (6 sections).",
}
_ACCEPT = ["txt", "text", "fountain", "spmd", "fdx", "pdf"]


def main() -> None:
    """Streamlit entry point."""
    try:
        import streamlit as st
    except ImportError as exc:
        raise ImportError(
            "Web UI needs the 'web' extra: .venv/bin/pip install .[web]"
        ) from exc

    from script2prompt.core import config as config_mod
    from script2prompt.core import llm, pipeline, scenes as scenes_mod
    from script2prompt.core.characters import Character, build_bible, title
    from script2prompt.core.modes import MODES

    cfg = config_mod.load()
    st.set_page_config(page_title="Script2Prompt", layout="wide")
    st.title("Script2Prompt")
    st.caption("Screenplay → Minimax H3 video prompts")

    uploaded = st.file_uploader("Screenplay", type=_ACCEPT)
    if uploaded is None:
        st.info("Upload a screenplay (.txt, .fountain, .fdx, .pdf) to begin.")
        return

    elements = pipeline.parse_bytes(uploaded.getvalue(), uploaded.name)
    found = scenes_mod.split(elements)

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Project settings")
        default_mode = cfg["project"]["mode"]
        mode = st.radio(
            "H3 mode (locked for this project)",
            MODES,
            index=MODES.index(default_mode) if default_mode in MODES else 0,
        )
        st.caption(MODE_HELP.get(mode, ""))
        style = st.text_input("Style", cfg["project"]["style"])
        duration = st.slider(
            "Target chunk seconds", 5.0, 10.0, float(cfg["project"]["duration"]), 0.5
        )
        shots_max = st.slider("Max shots per chunk", 1, 3, int(cfg["project"]["shots_max"]))
        use_llm = st.checkbox("Rewrite with the LLM endpoint (else templates)", value=False)

    with right:
        st.subheader(f"Parsed scenes: {len(found)}")
        for i, scene in enumerate(found, start=1):
            st.markdown(f"**Scene {i}** — {scene.get('context') or '(cold open)'}")
        st.subheader("Character bible (editable)")
        bible = []
        for idx, char in enumerate(build_bible(found)):
            cols = st.columns([1, 1, 3])
            name = cols[0].text_input("Name", title(char.name), key=f"name{idx}")
            sid = cols[1].text_input("Speaker", char.speaker_id or "", key=f"sid{idx}")
            desc = cols[2].text_input("Description", char.description, key=f"desc{idx}")
            bible.append(Character(name.upper(), sid or None, desc))

    if not st.button("Generate prompts", type="primary"):
        return

    project = pipeline.run(
        elements, mode=mode, duration=duration, shots_max=shots_max,
        style=style, bible=bible, rewrite=llm.rewrite if use_llm else None,
    )

    bad = [res.index for res in project.results if res.issues]
    if bad:
        st.warning(f"Validation issues in chunk(s): {bad}")

    for res in project.results:
        st.markdown(f"### Chunk {res.index} — {mode} ({res.chunk['duration']:.2f}s)")
        if res.scene:
            st.caption(f"Scene: {res.scene}")
        if res.issues:
            st.error("; ".join(res.issues))
        st.code(res.prompt, language="text")

    if mode != "T2VA":
        st.subheader("Reference manifest")
        st.json(pipeline.reference_manifest(project))

    st.subheader("Export")
    pack = pipeline.export_pack(project)
    for name, content in pack.items():
        st.download_button(f"Download {name}", content, file_name=name)
    if st.button("Write pack to ./out"):
        written = pipeline.write_pack(project, "out")
        st.success(f"Wrote {len(written)} files to ./out")


if __name__ == "__main__":
    main()
