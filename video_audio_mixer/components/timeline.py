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


def _time_marker(marker: dict) -> rx.Component:
    """A single time ruler tick + label."""
    return rx.el.div(
        rx.el.div(class_name="w-px h-2 bg-neutral-500"),
        rx.el.span(
            marker["label"],
            class_name="text-[9px] text-neutral-500 select-none whitespace-nowrap",
        ),
        class_name="absolute top-0 flex flex-col items-center -translate-x-1/2",
        style={"left": marker["pct"].to(str) + "%"},
    )


def timeline() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                "Timeline",
                class_name="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-3",
            ),
            # ── Outer wrapper: ruler + tracks share a relative parent for the playhead ──
            rx.el.div(
                # ── Time ruler row (clickable / draggable) ──
                rx.el.div(
                    # Gutter spacer (same width as track labels)
                    rx.el.div(class_name="w-32 shrink-0"),
                    # Ruler area
                    rx.el.div(
                        rx.foreach(MixerState.time_markers, _time_marker),
                        class_name="flex-1 relative h-5",
                    ),
                    custom_attrs={"id": "timeline-ruler"},
                    class_name="flex border-b border-neutral-800 mb-1 cursor-pointer select-none",
                    on_click=rx.call_script("window._timelineClick(event)"),
                ),
                # ── Tracks + playhead container ──
                rx.el.div(
                    # Video Audio track
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
                    # Audio tracks
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
                    # ── Playhead (vertical line spanning all tracks) ──
                    rx.el.div(
                        # Handle (triangle at the top)
                        rx.el.div(
                            class_name="w-3 h-3 bg-red-500 rotate-45 -translate-x-1/2 -translate-y-1/2 rounded-sm",
                            style={"position": "absolute", "top": "-2px", "left": "0"},
                        ),
                        # Vertical line
                        rx.el.div(
                            class_name="w-0.5 bg-red-500 absolute top-0 left-0 -translate-x-1/2",
                            style={"height": "100%"},
                        ),
                        custom_attrs={"id": "timeline-playhead"},
                        class_name="absolute top-0 z-20 pointer-events-none",
                        style={
                            "left": "0%",
                            "height": "100%",
                            "display": "none",
                        },
                    ),
                    custom_attrs={"id": "timeline-tracks"},
                    class_name="relative flex flex-col overflow-y-auto max-h-64 cursor-pointer",
                    on_click=rx.call_script(
                        "window._timelineClick(event)"
                    ),
                ),
                class_name="flex flex-col",
            ),
            # ── Current time display ──
            rx.el.div(
                rx.el.span(
                    custom_attrs={"id": "timeline-current-time"},
                    class_name="text-xs text-neutral-400 tabular-nums",
                ),
                class_name="mt-2 flex justify-end",
            ),
            class_name="bg-neutral-900 rounded-xl p-5 border border-neutral-800 shadow-lg w-full",
        ),
        class_name="w-full mt-6",
    )