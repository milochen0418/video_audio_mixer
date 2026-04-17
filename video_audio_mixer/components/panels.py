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
                    class_name="w-full rounded-lg bg-black aspect-video object-contain",
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


def audio_track_item(track: dict) -> rx.Component:
    return rx.el.div(
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
            rx.el.button(
                rx.icon(
                    "trash-2",
                    class_name="w-4 h-4 text-neutral-500 hover:text-red-400 transition-colors",
                ),
                on_click=lambda: MixerState.remove_audio_track(track["id"]),
                class_name="p-1 rounded hover:bg-neutral-700 transition-colors shrink-0",
            ),
            class_name="flex items-center",
        ),
        class_name="bg-neutral-800 p-3 rounded-md border border-neutral-700 group hover:border-neutral-600 transition-colors",
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