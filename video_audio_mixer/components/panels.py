import reflex as rx
from video_audio_mixer.states.mixer_state import MixerState


def video_panel() -> rx.Component:
    return rx.el.div(
        rx.el.h2(
            "Video Track",
            class_name="text-sm font-semibold text-neutral-400 mb-4 uppercase tracking-wider",
        ),
        rx.cond(
            MixerState.video_file == "",
            rx.upload.root(
                rx.el.div(
                    rx.icon("video", class_name="w-8 h-8 text-neutral-500 mb-3"),
                    rx.el.p(
                        "Drag and drop a video file",
                        class_name="text-sm text-neutral-300 font-medium",
                    ),
                    rx.el.p(
                        "or click to browse", class_name="text-xs text-neutral-500 mt-1"
                    ),
                    class_name="flex flex-col items-center justify-center border-2 border-dashed border-neutral-700 rounded-lg p-10 hover:border-indigo-500 hover:bg-neutral-800/50 transition-all cursor-pointer h-64",
                ),
                id="video_upload",
                accept={"video/*": [".mp4", ".mov", ".mkv", ".webm"]},
                on_drop=MixerState.handle_video_upload(
                    rx.upload_files(upload_id="video_upload")
                ),
            ),
            rx.el.div(
                rx.el.video(
                    src=rx.get_upload_url(MixerState.video_file),
                    controls=True,
                    custom_attrs={"id": "preview-video"},
                    class_name="w-full rounded-lg bg-black aspect-video object-contain",
                ),
                # Hidden div holding serialized preview data for JS
                rx.el.div(
                    MixerState.preview_data_json,
                    custom_attrs={"id": "preview-data"},
                    display="none",
                ),
                # Preview controls
                rx.el.div(
                    rx.cond(
                        MixerState.is_previewing,
                        rx.el.button(
                            rx.icon("square", class_name="w-4 h-4 mr-2"),
                            "Stop Preview",
                            on_click=[
                                rx.call_script("window.stopPreview()"),
                                MixerState.stop_preview,
                            ],
                            class_name="flex items-center bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors",
                        ),
                        rx.el.button(
                            rx.icon("play", class_name="w-4 h-4 mr-2"),
                            "Preview Mix",
                            on_click=[
                                rx.call_script("window.startPreviewFromDOM()"),
                                MixerState.preview_mix,
                            ],
                            disabled=MixerState.audio_tracks.length() == 0,
                            class_name=rx.cond(
                                MixerState.audio_tracks.length() == 0,
                                "flex items-center bg-emerald-600/50 cursor-not-allowed text-white/60 px-4 py-2 rounded-md text-sm font-medium",
                                "flex items-center bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors",
                            ),
                        ),
                    ),
                    rx.el.p(
                        "Plays video with all audio tracks mixed",
                        class_name="text-[11px] text-neutral-500",
                    ),
                    class_name="mt-3 flex items-center gap-3",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.span("Filename:", class_name="text-xs text-neutral-500"),
                        rx.el.span(
                            MixerState.video_filename,
                            class_name="text-xs font-medium truncate ml-2",
                        ),
                        class_name="flex items-center",
                    ),
                    rx.el.div(
                        rx.el.span("Duration:", class_name="text-xs text-neutral-500"),
                        rx.el.span(
                            f"{MixerState.video_duration}s",
                            class_name="text-xs font-medium ml-2",
                        ),
                        class_name="flex items-center",
                    ),
                    class_name="mt-3 flex justify-between bg-neutral-800/50 p-3 rounded-md border border-neutral-800",
                ),
                class_name="flex flex-col",
            ),
        ),
        class_name="flex-1 bg-neutral-900 rounded-xl p-5 border border-neutral-800 shadow-lg min-w-0",
    )


def _labeled_number_input(
    label: str, value, on_change, min_val: float = 0.0, max_val: float = 9999.0, step: float = 0.1, suffix: str = "",
) -> rx.Component:
    """A compact labeled number input."""
    return rx.el.div(
        rx.el.label(label, class_name="text-[10px] text-neutral-500 uppercase tracking-wider"),
        rx.el.div(
            rx.el.input(
                type="number",
                value=value,
                min=min_val,
                max=max_val,
                step=step,
                on_change=on_change,
                class_name="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none",
            ),
            rx.cond(
                suffix != "",
                rx.el.span(suffix, class_name="text-[10px] text-neutral-500 ml-1"),
                rx.fragment(),
            ),
            class_name="flex items-center",
        ),
        class_name="flex flex-col gap-0.5",
    )


def _keyframe_row_selected(kf: dict, index: int) -> rx.Component:
    """A single row for editing a volume keyframe of the selected track."""
    return rx.el.div(
        rx.el.span(
            "#" + (index + 1).to(str),
            class_name="text-[10px] text-neutral-500 w-5 shrink-0",
        ),
        rx.el.input(
            type="number",
            value=kf["time"],
            min=0,
            step=0.1,
            on_change=lambda v: MixerState.update_volume_keyframe(
                MixerState.selected_track_id, index, v, kf["volume"]
            ),
            class_name="w-16 bg-neutral-900 border border-neutral-700 rounded px-1.5 py-0.5 text-[11px] text-neutral-200 focus:outline-none focus:border-indigo-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none",
            title="Time (seconds)",
        ),
        rx.el.span("s", class_name="text-[10px] text-neutral-500"),
        rx.el.input(
            type="range",
            min="0",
            max="2",
            step="0.01",
            value=kf["volume"],
            on_change=lambda v: MixerState.update_volume_keyframe(
                MixerState.selected_track_id, index, kf["time"], v
            ),
            class_name="flex-1 h-1 accent-emerald-500 cursor-pointer",
        ),
        rx.el.span(
            kf["volume"].to(str) + "x",
            class_name="text-[10px] text-neutral-300 w-8 text-right tabular-nums",
        ),
        rx.el.button(
            rx.icon("x", class_name="w-3 h-3"),
            on_click=lambda: MixerState.remove_volume_keyframe(
                MixerState.selected_track_id, index
            ),
            class_name="p-0.5 rounded text-neutral-500 hover:text-red-400 hover:bg-neutral-700 transition-colors shrink-0",
            title="Remove keyframe",
        ),
        class_name="flex items-center gap-1.5 bg-neutral-800/50 rounded px-1.5 py-1 border border-neutral-700/50",
    )


def audio_track_item(track: dict) -> rx.Component:
    is_selected = MixerState.selected_track_id == track["id"]
    is_muted = track.get("muted", False)
    is_solo = track.get("solo", False)

    return rx.el.div(
        # Header row: icon, name, duration, action buttons
        rx.el.div(
            rx.el.div(
                rx.icon("music", class_name="w-4 h-4 text-emerald-400 shrink-0"),
                rx.el.div(
                    rx.el.p(
                        track["filename"],
                        class_name="text-sm font-medium text-neutral-200 truncate",
                    ),
                    rx.el.p(
                        f"Duration: {track['duration']}s",
                        class_name="text-xs text-neutral-500",
                    ),
                    class_name="min-w-0 flex-1 mx-3",
                ),
                class_name="flex items-center min-w-0 flex-1",
            ),
            rx.el.div(
                # Expand/collapse toggle
                rx.el.button(
                    rx.cond(
                        is_selected,
                        rx.icon("chevron-up", class_name="w-4 h-4"),
                        rx.icon("chevron-down", class_name="w-4 h-4"),
                    ),
                    on_click=lambda: MixerState.select_track(track["id"]),
                    class_name="p-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700 transition-colors",
                    title="Edit track",
                ),
                # Duplicate
                rx.el.button(
                    rx.icon("copy", class_name="w-4 h-4"),
                    on_click=lambda: MixerState.duplicate_track(track["id"]),
                    class_name="p-1 rounded text-neutral-400 hover:text-indigo-400 hover:bg-neutral-700 transition-colors",
                    title="Duplicate track",
                ),
                # Delete
                rx.el.button(
                    rx.icon("trash-2", class_name="w-4 h-4"),
                    on_click=lambda: MixerState.remove_audio_track(track["id"]),
                    class_name="p-1 rounded text-neutral-400 hover:text-red-400 hover:bg-neutral-700 transition-colors",
                    title="Remove track",
                ),
                class_name="flex items-center gap-0.5 shrink-0",
            ),
            class_name="flex items-center justify-between",
        ),
        # Expanded editing controls
        rx.cond(
            is_selected,
            rx.el.div(
                # Mute / Solo row
                rx.el.div(
                    rx.el.button(
                        rx.icon("volume-x", class_name="w-3.5 h-3.5 mr-1"),
                        "Mute",
                        on_click=lambda: MixerState.toggle_track_mute(track["id"]),
                        class_name=rx.cond(
                            is_muted,
                            "flex items-center text-xs font-medium px-2.5 py-1 rounded bg-red-500/20 text-red-400 border border-red-500/30",
                            "flex items-center text-xs font-medium px-2.5 py-1 rounded bg-neutral-800 text-neutral-400 border border-neutral-700 hover:border-neutral-600",
                        ),
                    ),
                    rx.el.button(
                        rx.icon("headphones", class_name="w-3.5 h-3.5 mr-1"),
                        "Solo",
                        on_click=lambda: MixerState.toggle_track_solo(track["id"]),
                        class_name=rx.cond(
                            is_solo,
                            "flex items-center text-xs font-medium px-2.5 py-1 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30",
                            "flex items-center text-xs font-medium px-2.5 py-1 rounded bg-neutral-800 text-neutral-400 border border-neutral-700 hover:border-neutral-600",
                        ),
                    ),
                    class_name="flex gap-2",
                ),
                # Volume slider
                rx.el.div(
                    rx.el.label(
                        "Volume",
                        class_name="text-[10px] text-neutral-500 uppercase tracking-wider",
                    ),
                    rx.el.div(
                        rx.el.input(
                            type="range",
                            min="0",
                            max="2",
                            step="0.01",
                            value=track["volume"],
                            on_change=lambda v: MixerState.update_track_volume(
                                track["id"], v
                            ),
                            class_name="flex-1 h-1.5 accent-indigo-500 cursor-pointer",
                        ),
                        rx.el.span(
                            track["volume"].to(str) + "x",
                            class_name="text-xs text-neutral-300 w-10 text-right tabular-nums",
                        ),
                        class_name="flex items-center gap-2",
                    ),
                    class_name="flex flex-col gap-1",
                ),
                # Volume Envelope (keyframes)
                rx.el.div(
                    rx.el.div(
                        rx.el.label(
                            "Volume Envelope",
                            class_name="text-[10px] text-neutral-500 uppercase tracking-wider",
                        ),
                        rx.el.button(
                            rx.icon("plus", class_name="w-3 h-3 mr-0.5"),
                            "Add",
                            on_click=lambda: MixerState.add_volume_keyframe(
                                track["id"],
                                track.get("trim_end", track["duration"]),
                                1.0,
                            ),
                            class_name="flex items-center text-[10px] font-medium text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 px-1.5 py-0.5 rounded border border-indigo-500/30 transition-colors",
                        ),
                        class_name="flex items-center justify-between mb-1",
                    ),
                    rx.foreach(
                        MixerState.selected_track_keyframes,
                        lambda kf, idx: _keyframe_row_selected(kf, idx),
                    ),
                    class_name="flex flex-col gap-1",
                ),
                # Timing controls: start time, trim start, trim end
                rx.el.div(
                    _labeled_number_input(
                        "Start Time (s)",
                        track.get("start_time", 0.0),
                        lambda v: MixerState.update_track_start_time(
                            track["id"], v
                        ),
                        min_val=0.0,
                        step=0.1,
                    ),
                    _labeled_number_input(
                        "Trim Start (s)",
                        track.get("trim_start", 0.0),
                        lambda v: MixerState.update_track_trim_start(
                            track["id"], v
                        ),
                        min_val=0.0,
                        max_val=track["duration"],
                        step=0.1,
                    ),
                    _labeled_number_input(
                        "Trim End (s)",
                        track.get("trim_end", track["duration"]),
                        lambda v: MixerState.update_track_trim_end(
                            track["id"], v
                        ),
                        min_val=0.0,
                        max_val=track["duration"],
                        step=0.1,
                    ),
                    class_name="grid grid-cols-3 gap-3",
                ),
                class_name="flex flex-col gap-3 mt-3 pt-3 border-t border-neutral-700",
            ),
            rx.fragment(),
        ),
        class_name=rx.cond(
            is_selected,
            "bg-neutral-800 p-3 rounded-md border border-indigo-500/50 transition-colors",
            "bg-neutral-800 p-3 rounded-md border border-neutral-700 hover:border-neutral-600 transition-colors",
        ),
    )


def audio_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                "Audio Tracks",
                class_name="text-sm font-semibold text-neutral-400 uppercase tracking-wider",
            ),
            rx.upload.root(
                rx.el.button(
                    rx.icon("plus", class_name="w-4 h-4 mr-1"),
                    "Add Track",
                    class_name="flex items-center text-xs font-medium text-neutral-300 bg-neutral-800 hover:bg-neutral-700 px-3 py-1.5 rounded border border-neutral-700 transition-colors",
                ),
                id="audio_upload",
                accept={"audio/*": [".mp3", ".wav", ".ogg", ".m4a"]},
                multiple=True,
                on_drop=MixerState.handle_audio_upload(
                    rx.upload_files(upload_id="audio_upload")
                ),
            ),
            class_name="flex justify-between items-center mb-4",
        ),
        rx.cond(
            MixerState.audio_tracks.length() > 0,
            rx.el.div(
                rx.foreach(MixerState.audio_tracks, audio_track_item),
                class_name="flex flex-col gap-2 overflow-y-auto pr-1 custom-scrollbar",
            ),
            rx.el.div(
                rx.icon("audio-lines", class_name="w-8 h-8 text-neutral-600 mb-2"),
                rx.el.p(
                    "No audio tracks added",
                    class_name="text-sm text-neutral-500 text-center",
                ),
                class_name="flex flex-col items-center justify-center py-12 border border-dashed border-neutral-800 rounded-lg bg-neutral-900/50",
            ),
        ),
        class_name="w-full lg:w-80 shrink-0 bg-neutral-900 rounded-xl p-5 border border-neutral-800 shadow-lg flex flex-col",
    )