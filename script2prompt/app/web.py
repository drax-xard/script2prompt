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
    from script2prompt.core import llm, pipeline
    from script2prompt.core import scenes as scenes_mod
    from script2prompt.core.characters import build_bible
    from script2prompt.core.modes import MODES

    cfg = config_mod.load()
    st.set_page_config(page_title="Script2Prompt", layout="wide")
    st.title("Script2Prompt")
    st.caption("Screenplay → Minimax H3 video prompts")

    uploaded = st.file_uploader("Screenplay", type=_ACCEPT)
    if uploaded is None:
        st.info("Upload a screenplay (.txt, .fountain, .fdx, .pdf) to begin.")
        return

    fingerprint = f"{uploaded.name}:{uploaded.size}"
    cache = st.session_state.setdefault("_parsed", {})
    if fingerprint in cache:
        elements, found = cache[fingerprint]
    else:
        elements = pipeline.parse_bytes(uploaded.getvalue(), uploaded.name)
        found = scenes_mod.split(elements)
        cache.clear()
        cache[fingerprint] = (elements, found)

    settings = pipeline.default_settings(cfg)
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Project settings")
        mode = st.radio(
            "H3 mode (locked for this project)",
            MODES,
            index=MODES.index(settings["mode"]),
        )
        st.caption(MODE_HELP.get(mode, ""))
        style = st.text_input("Style", settings["style"])
        duration = st.slider(
            "Target chunk seconds", 5.0, 10.0, float(settings["duration"]), 0.5
        )
        shots_max = st.slider("Max shots per chunk", 1, 3, int(settings["shots_max"]))
        use_llm = st.checkbox("Rewrite with the LLM endpoint (else templates)", value=False)

    with right:
        st.subheader(f"Parsed scenes: {len(found)}")
        for i, scene in enumerate(found, start=1):
            st.markdown(f"**Scene {i}** — {scene.get('context') or '(cold open)'}")
        st.subheader("Character bible (editable)")
        rows = pipeline.bible_rows(build_bible(found))
        for idx, row in enumerate(rows):
            cols = st.columns([1, 1, 3])
            row["name"] = cols[0].text_input("Name", row["name"], key=f"name{idx}")
            row["speaker_id"] = cols[1].text_input("Speaker", row["speaker_id"], key=f"sid{idx}")
            row["description"] = cols[2].text_input("Description", row["description"], key=f"desc{idx}")
        bible = pipeline.bible_from_rows(rows)

    if not st.button("Generate prompts", type="primary"):
        project = st.session_state.get("project")
        if project is None or st.session_state.get("fingerprint") != fingerprint:
            return
    else:
        rewrite = (
            llm.Rewriter(elements, bible, context=cfg["llm"].get("context", True), style=style)
            if use_llm
            else None
        )
        project = pipeline.run(
            elements, mode=mode, duration=duration, shots_max=shots_max,
            style=style, bible=bible, rewrite=rewrite,
        )
        st.session_state["project"] = project
        st.session_state["fingerprint"] = fingerprint

    warnings = pipeline.lint(project)
    summary = pipeline.budgets(project)

    st.subheader("Budget")
    m1, m2, m3 = st.columns(3)
    m1.metric("Chunks", len(project.results))
    m2.metric("Total duration", f"{summary['total_duration']:.2f}s")
    m3.metric("Characters", len(project.bible))
    for ch in summary["chunks"]:
        st.caption(
            f"Chunk {ch['index']}: {ch['chars']}/{summary['char_budget']} chars, "
            f"{ch['duration']:.2f}s, {ch['shots']} shot(s)"
        )
        st.progress(min(ch["char_ratio"], 1.0))
    if summary["over_budget"]:
        st.error(f"Over the {summary['char_budget']}-char budget: {summary['over_budget']}")

    if warnings:
        with st.expander(f"Lint warnings ({len(warnings)})", expanded=True):
            for warning in warnings:
                st.warning(warning)
    else:
        st.success("Lint: no warnings")

    for res in project.results:
        st.markdown(f"### Chunk {res.index} — {project.mode} ({res.chunk['duration']:.2f}s)")
        if res.scene:
            st.caption(f"Scene: {res.scene}")
        if res.issues:
            st.error("; ".join(res.issues))
        st.code(res.prompt, language="text")

    if project.mode != "T2VA":
        st.subheader("Reference manifest")
        st.json(pipeline.reference_manifest(project))

    st.subheader("Export")
    pack = pipeline.export_pack(project)
    for name, content in pack.items():
        st.download_button(f"Download {name}", content, file_name=name)
    if st.button("Write pack to ./out"):
        written = pipeline.write_pack(project, "out")
        st.success(f"Wrote {len(written)} files to ./out: {', '.join(written)}")


if __name__ == "__main__":
    main()
