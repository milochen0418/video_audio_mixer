import reflex as rx
from video_audio_mixer.states.mixer_state import MixerState


def volume_segment(segment: dict, index: int) -> rx.Component:
    return rx.el.div(
        style={
            "left": f"calc(({segment['start']} / {MixerState.video_duration}) * 100%)",
            "width": f"calc((({segment['end']} - {segment['start']}) / {MixerState.video_duration}) * 100%)",
            "height": f"calc({segment['volume']} * 50%)",
            "bottom": "0",
        },
        class_name=rx.cond(
            segment["volume"] > 1.0,
            "absolute bg-indigo-400/60 border-t border-indigo-300 hover:bg-indigo-300/80 transition-colors cursor-pointer",
            "absolute bg-indigo-500/60 border-t border-indigo-400 hover:bg-indigo-400/80 transition-colors cursor-pointer",
        ),
        on_click=lambda: MixerState.add_volume_segment(
            segment["start"] + (segment["end"] - segment["start"]) / 2
        ),
    )


def timeline() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                "Timeline",
                class_name="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4",
            ),
            rx.el.div(
                rx.el.div(class_name="h-full border-l border-neutral-700 ml-[10%]"),
                rx.el.div(class_name="h-full border-l border-neutral-700 ml-[10%]"),
                rx.el.div(class_name="h-full border-l border-neutral-700 ml-[10%]"),
                class_name="w-full h-6 border-b border-neutral-800 flex items-end mb-2 relative opacity-50",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        "Video Audio",
                        class_name="w-32 shrink-0 bg-neutral-800 text-xs font-medium text-neutral-300 p-2 flex items-center border-r border-neutral-700",
                    ),
                    rx.el.div(
                        rx.cond(
                            MixerState.video_duration > 0,
                            rx.el.div(
                                rx.foreach(MixerState.volume_segments, volume_segment),
                                class_name="h-full bg-indigo-900/20 border border-indigo-900/50 rounded w-full relative",
                            ),
                            rx.el.div(
                                class_name="h-full w-full bg-neutral-800/30 rounded border border-neutral-800 border-dashed"
                            ),
                        ),
                        class_name="flex-1 relative p-1",
                    ),
                    class_name="flex h-12 bg-neutral-900 border border-neutral-800 rounded-md overflow-hidden mb-2",
                ),
                rx.foreach(
                    MixerState.audio_tracks,
                    lambda track: rx.el.div(
                        rx.el.div(
                            rx.el.span(track["filename"], class_name="truncate w-20"),
                            rx.el.div(
                                rx.el.button(
                                    rx.cond(
                                        track.get("muted", False),
                                        rx.icon("volume-x", class_name="w-3 h-3"),
                                        rx.icon("volume-2", class_name="w-3 h-3"),
                                    ),
                                    on_click=lambda: MixerState.toggle_track_mute(
                                        track["id"]
                                    ),
                                    class_name=rx.cond(
                                        track.get("muted", False),
                                        "text-red-400 p-0.5 rounded hover:bg-neutral-700",
                                        "text-neutral-400 hover:text-neutral-200 p-0.5 rounded hover:bg-neutral-700",
                                    ),
                                    title="Toggle mute",
                                ),
                                rx.el.button(
                                    rx.icon("headphones", class_name="w-3 h-3"),
                                    on_click=lambda: MixerState.toggle_track_solo(
                                        track["id"]
                                    ),
                                    class_name=rx.cond(
                                        track.get("solo", False),
                                        "text-amber-400 p-0.5 rounded hover:bg-neutral-700",
                                        "text-neutral-400 hover:text-neutral-200 p-0.5 rounded hover:bg-neutral-700",
                                    ),
                                    title="Toggle solo",
                                ),
                                class_name="flex gap-0.5",
                            ),
                            class_name="w-32 shrink-0 bg-neutral-800 text-xs font-medium text-neutral-300 p-2 flex items-center justify-between border-r border-neutral-700",
                        ),
                        rx.el.div(
                            rx.el.div(
                                # Display volume percentage inside the track bar
                                rx.el.span(
                                    track["volume"].to(str) + "x",
                                    class_name="text-[10px] text-white/60 px-1 select-none",
                                ),
                                class_name=rx.cond(
                                    track.get("muted", False),
                                    "h-full bg-neutral-700/40 border border-neutral-600 rounded absolute flex items-center",
                                    "h-full bg-emerald-900/40 border border-emerald-700 rounded absolute flex items-center",
                                ),
                                style=rx.cond(
                                    MixerState.video_duration > 0,
                                    {
                                        "left": f"calc(({track.get('start_time', 0)} / {MixerState.video_duration}) * 100%)",
                                        "width": f"calc((({track.get('trim_end', track['duration'])} - {track.get('trim_start', 0)}) / {MixerState.video_duration}) * 100%)",
                                    },
                                    {"width": "30%"},
                                ),
                            ),
                            class_name="flex-1 relative p-1",
                        ),
                        class_name="flex h-12 bg-neutral-900 border border-neutral-800 rounded-md overflow-hidden mb-2",
                    ),
                ),
                class_name="flex flex-col overflow-y-auto max-h-64",
            ),
            class_name="bg-neutral-900 rounded-xl p-5 border border-neutral-800 shadow-lg w-full",
        ),
        class_name="w-full mt-6",
    )