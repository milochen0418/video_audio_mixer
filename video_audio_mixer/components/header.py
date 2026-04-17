import reflex as rx
from video_audio_mixer.states.mixer_state import MixerState


def header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.icon("sliders-horizontal", class_name="w-6 h-6 text-indigo-400"),
                rx.el.h1(
                    "Video Audio Mixer", class_name="text-xl font-bold tracking-tight"
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.cond(
                    MixerState.exported_file != "",
                    rx.el.button(
                        rx.icon("download", class_name="w-4 h-4 mr-2"),
                        "Download",
                        on_click=rx.download(
                            url=rx.get_upload_url(MixerState.exported_file),
                            filename=MixerState.exported_file,
                        ),
                        class_name="flex items-center bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors mr-3",
                    ),
                ),
                rx.el.button(
                    rx.cond(
                        MixerState.is_exporting,
                        rx.el.div(
                            rx.icon("loader", class_name="w-4 h-4 mr-2 animate-spin"),
                            rx.el.span(
                                f"Exporting {MixerState.export_progress.to(int)}%"
                            ),
                            class_name="flex items-center",
                        ),
                        rx.el.div(
                            rx.icon("film", class_name="w-4 h-4 mr-2"),
                            rx.el.span("Export Video"),
                            class_name="flex items-center",
                        ),
                    ),
                    on_click=MixerState.export_video,
                    disabled=MixerState.is_exporting | (MixerState.video_file == ""),
                    class_name=rx.cond(
                        MixerState.is_exporting | (MixerState.video_file == ""),
                        "flex items-center bg-indigo-600/50 cursor-not-allowed text-white/70 px-4 py-2 rounded-md text-sm font-medium",
                        "flex items-center bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors",
                    ),
                ),
                class_name="flex items-center",
            ),
            class_name="flex justify-between items-center w-full max-w-screen-2xl mx-auto px-6 h-16",
        ),
        class_name="bg-neutral-900 border-b border-neutral-800 sticky top-0 z-50 shadow-sm",
    )