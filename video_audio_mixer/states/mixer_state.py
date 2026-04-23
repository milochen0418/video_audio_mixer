import asyncio
import json
import logging
import random
import string
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import reflex as rx
import yt_dlp


class _QuietYtDlpLogger:
    def debug(self, msg):
        return

    def info(self, msg):
        return

    def warning(self, msg):
        return

    def error(self, msg):
        logging.error(msg)


def get_media_duration(file_path: str) -> float:
    """Extract media duration using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception as e:
        logging.exception(f"Error getting duration: {e}")
        return 0.0


def _interpolate_envelope(kfs: list, t: float) -> float:
    """Linearly interpolate volume envelope from keyframes at time t."""
    if not kfs:
        return 1.0
    if t <= kfs[0]["time"]:
        return max(0.0, kfs[0]["volume"])
    if t >= kfs[-1]["time"]:
        return max(0.0, kfs[-1]["volume"])
    for j in range(len(kfs) - 1):
        k0, k1 = kfs[j], kfs[j + 1]
        if k0["time"] <= t <= k1["time"]:
            span = k1["time"] - k0["time"]
            frac = (t - k0["time"]) / span if span > 0 else 0
            return max(0.0, k0["volume"] + frac * (k1["volume"] - k0["volume"]))
    return 1.0


def _sanitize_filename_component(value: str) -> str:
    safe_value = "".join(c for c in value if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe_value or "youtube_audio"


def _build_audio_track_entry(file_path: Path, display_name: str) -> dict[str, Any]:
    duration = get_media_duration(str(file_path.absolute()))
    track_id = f"trk_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
    return {
        "id": track_id,
        "filename": display_name,
        "path": file_path.name,
        "volume": 1.0,
        "start_time": 0.0,
        "end_time": duration,
        "duration": duration,
        "muted": False,
        "solo": False,
        "volume_keyframes": [
            {"time": 0.0, "volume": 1.0},
        ],
    }


def _build_youtube_ydl_options() -> dict[str, Any]:
    return {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": _QuietYtDlpLogger(),
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "android", "ios"],
            }
        },
        "remote_components": ["ejs:github"],
        "no_color": True,
        "geo_bypass": True,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "retry_sleep_functions": {"http": lambda n: 0.5 * n},
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        "extract_flat": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
    }
def _extract_youtube_audio_metadata(url: str) -> tuple[str, str]:
    """Extract a YouTube title and video id without downloading media."""
    with yt_dlp.YoutubeDL(_build_youtube_ydl_options()) as ydl:
        info_dict = ydl.extract_info(url, download=False)
    return info_dict.get("title", "youtube_audio"), info_dict.get("id", "unknown")


def _download_youtube_audio(
    url: str,
    upload_dir: Path,
    video_title: str,
    video_id: str,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path, str]:
    """Download a YouTube URL as MP3 into the upload directory."""
    base_opts = _build_youtube_ydl_options()
    safe_title = _sanitize_filename_component(video_title)
    if safe_title == "youtube_audio":
        safe_title = f"video_{video_id}"

    download_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    output_prefix = f"yt_{download_id}_{safe_title}"
    output_base = upload_dir / output_prefix

    download_opts = {
        **base_opts,
        "outtmpl": {"default": str(output_base) + ".%(ext)s"},
    }
    if progress_hook is not None:
        download_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(download_opts) as download_ydl:
        download_ydl.download([url])

    final_path = output_base.with_suffix(".mp3")
    if not final_path.exists():
        candidates = sorted(upload_dir.glob(f"{output_prefix}*.mp3"))
        if candidates:
            final_path = candidates[0]

    if not final_path.exists():
        raise FileNotFoundError(f"Unable to locate the downloaded MP3 for {url}")

    return final_path, f"{safe_title}.mp3"


def _youtube_import_error_message(error: Exception) -> str:
    error_str = str(error).lower()
    if "sign in to confirm you're not a bot" in error_str or "authentication" in error_str:
        return "This video needs authentication or is restricted. Please try another URL."
    if "http error 403" in error_str or "unable to download video data" in error_str:
        return "YouTube blocked the stream. Please try again later or choose a different video."
    if "signature extraction failed" in error_str or "empty" in error_str:
        return "Failed to extract the audio stream. Please try again later."
    if "unavailable" in error_str or "private" in error_str:
        return "This video is unavailable, private, or has been removed."
    if "copyright" in error_str:
        return "This video cannot be downloaded because of copyright restrictions."
    return f"Unable to import audio from that URL: {error}"


class MixerState(rx.State):
    video_file: str = ""
    video_filename: str = ""
    video_duration: float = 0.0
    video_size: str = ""
    audio_tracks: list[dict[str, Any]] = []
    volume_segments: list[dict[str, float]] = []
    selected_track_id: str = ""
    is_uploading: bool = False
    show_add_track_menu: bool = False
    show_youtube_import_form: bool = False
    youtube_import_url: str = ""
    youtube_import_error: str = ""
    youtube_import_detail: str = ""
    youtube_import_notice_visible: bool = False
    youtube_import_notice_expanded: bool = False
    youtube_import_notice_kind: str = "info"
    youtube_import_status: str = ""
    youtube_import_progress: float = 0.0
    youtube_import_progress_text: str = "0.00%"
    is_youtube_importing: bool = False
    is_exporting: bool = False
    is_previewing: bool = False
    export_progress: float = 0.0
    export_error: str = ""
    exported_file: str = ""

    @rx.event
    async def handle_video_upload(self, files: list[rx.UploadFile]):
        self.is_uploading = True
        yield
        try:
            for file in files:
                upload_data = await file.read()
                upload_dir = rx.get_upload_dir()
                upload_dir.mkdir(parents=True, exist_ok=True)
                unique_name = (
                    "".join(random.choices(string.ascii_letters + string.digits, k=10))
                    + "_"
                    + file.filename
                )
                file_path = upload_dir / unique_name
                with file_path.open("wb") as f:
                    f.write(upload_data)
                self.video_file = unique_name
                self.video_filename = file.filename
                self.video_size = f"{len(upload_data) / (1024 * 1024):.2f} MB"
                full_path = str(file_path.absolute())
                self.video_duration = get_media_duration(full_path)
                self.volume_segments = [
                    {"start": 0.0, "end": self.video_duration, "volume": 1.0}
                ]
        except Exception as e:
            logging.exception(f"Error handling video upload: {e}")
        finally:
            self.is_uploading = False

    @rx.event
    async def handle_audio_upload(self, files: list[rx.UploadFile]):
        self.is_uploading = True
        self.show_add_track_menu = False
        self.show_youtube_import_form = False
        self.youtube_import_error = ""
        self.youtube_import_status = ""
        yield
        try:
            for file in files:
                upload_data = await file.read()
                upload_dir = rx.get_upload_dir()
                upload_dir.mkdir(parents=True, exist_ok=True)
                unique_name = (
                    "".join(random.choices(string.ascii_letters + string.digits, k=10))
                    + "_"
                    + file.filename
                )
                file_path = upload_dir / unique_name
                with file_path.open("wb") as f:
                    f.write(upload_data)
                self.audio_tracks.append(_build_audio_track_entry(file_path, file.filename))
        except Exception as e:
            logging.exception(f"Error handling audio upload: {e}")
        finally:
            self.is_uploading = False

    @rx.event
    def toggle_add_track_menu(self):
        if self.show_add_track_menu:
            self.show_add_track_menu = False
            self.show_youtube_import_form = False
            self.youtube_import_error = ""
            self.youtube_import_status = ""
            self.youtube_import_progress = 0.0
        else:
            self.show_add_track_menu = True
            self.show_youtube_import_form = False
            self.youtube_import_error = ""
            self.youtube_import_status = ""
            self.youtube_import_progress = 0.0

    @rx.event
    def close_add_track_menu(self):
        self.show_add_track_menu = False
        self.show_youtube_import_form = False
        self.youtube_import_error = ""
        self.youtube_import_status = ""
        self.youtube_import_progress = 0.0

    @rx.event
    def open_youtube_import_form(self):
        self.show_add_track_menu = True
        self.show_youtube_import_form = True
        self.youtube_import_error = ""
        self.youtube_import_status = ""
        self.youtube_import_progress = 0.0

    @rx.event
    def back_to_add_track_choices(self):
        self.show_youtube_import_form = False
        self.youtube_import_error = ""
        self.youtube_import_status = ""
        self.youtube_import_progress = 0.0

    @rx.event
    def set_youtube_import_url(self, url: str):
        self.youtube_import_url = url
        if self.youtube_import_error:
            self.youtube_import_error = ""

    def _set_youtube_import_notice(
        self,
        kind: str,
        summary: str,
        detail: str,
        error: str = "",
        progress: float | None = None,
    ):
        self.youtube_import_notice_kind = kind
        self.youtube_import_status = summary
        self.youtube_import_detail = detail
        self.youtube_import_error = error
        self.youtube_import_notice_visible = True
        if progress is not None:
            self._set_youtube_import_progress(progress)

    def _set_youtube_import_progress(self, progress: float):
        self.youtube_import_progress = progress
        self.youtube_import_progress_text = f"{progress:.2f}%"

    @rx.event
    def dismiss_youtube_import_notice(self):
        self.youtube_import_notice_visible = False
        self.youtube_import_notice_expanded = False
        self.youtube_import_notice_kind = "info"
        self.youtube_import_status = ""
        self.youtube_import_detail = ""
        self.youtube_import_error = ""
        self.youtube_import_progress = 0.0

    @rx.event
    def toggle_youtube_import_notice_details(self):
        self.youtube_import_notice_expanded = not self.youtube_import_notice_expanded

    @rx.event
    async def handle_youtube_import(self):
        youtube_url = self.youtube_import_url.strip()
        if not youtube_url:
            self._set_youtube_import_notice(
                "error",
                "YouTube import failed",
                "Please paste a YouTube URL first.\n\nThe importer needs a valid YouTube URL before it can begin.",
                "Please paste a YouTube URL first.",
            )
            self.youtube_import_notice_expanded = True
            self._set_youtube_import_progress(0.0)
            yield
            return

        self.is_youtube_importing = True
        self.youtube_import_notice_expanded = False
        self._set_youtube_import_progress(0.0)
        self._set_youtube_import_notice(
            "loading",
            "Checking the YouTube link...",
            f"URL:\n{youtube_url}\n\nResolving metadata before downloading audio.",
            progress=0.0,
        )
        yield

        try:
            video_title, video_id = await asyncio.to_thread(
                _extract_youtube_audio_metadata,
                youtube_url,
            )
            self._set_youtube_import_notice(
                "loading",
                f"Downloading audio from {video_title}...",
                (
                    f"URL:\n{youtube_url}\n\n"
                    f"Title: {video_title}\n"
                    f"Video ID: {video_id}\n\n"
                    "Downloading MP3 into the upload directory."
                ),
                progress=0.0,
            )
            yield

            upload_dir = rx.get_upload_dir()
            upload_dir.mkdir(parents=True, exist_ok=True)
            download_snapshot: dict[str, Any] = {
                "progress": 0.0,
                "detail": "Preparing download...",
            }

            def _download_progress_hook(progress_data: dict[str, Any]) -> None:
                status = progress_data.get("status")
                if status == "finished":
                    download_snapshot["progress"] = 99.0
                    download_snapshot["detail"] = (
                        "Download complete. Converting the video to MP3..."
                    )
                    return
                if status != "downloading":
                    return
                downloaded_bytes = float(progress_data.get("downloaded_bytes") or 0.0)
                total_bytes = float(
                    progress_data.get("total_bytes")
                    or progress_data.get("total_bytes_estimate")
                    or 0.0
                )
                progress = 0.0
                if total_bytes > 0:
                    progress = min(99.0, max(0.0, downloaded_bytes / total_bytes * 100.0))
                detail = f"Progress: {progress:.2f}%"
                eta = progress_data.get("eta")
                if eta is not None:
                    detail += f" • ETA {int(eta)}s"
                download_snapshot["progress"] = progress
                download_snapshot["detail"] = detail

            download_task = asyncio.create_task(
                asyncio.to_thread(
                    _download_youtube_audio,
                    youtube_url,
                    upload_dir,
                    video_title,
                    video_id,
                    _download_progress_hook,
                )
            )
            last_rendered_progress = -1
            while not download_task.done():
                current_progress = float(download_snapshot["progress"])
                current_rendered_progress = int(current_progress)
                if current_rendered_progress != last_rendered_progress:
                    self._set_youtube_import_notice(
                        "loading",
                        f"Downloading audio from {video_title}...",
                        (
                            f"URL:\n{youtube_url}\n\n"
                            f"Title: {video_title}\n"
                            f"Video ID: {video_id}\n\n"
                            f"{download_snapshot['detail']}\n\n"
                            "Downloading MP3 into the upload directory."
                        ),
                        progress=current_progress,
                    )
                    last_rendered_progress = current_rendered_progress
                    yield
                await asyncio.sleep(0.2)

            file_path, display_name = await download_task
            self._set_youtube_import_progress(100.0)
            self.audio_tracks.append(_build_audio_track_entry(file_path, display_name))
            self.youtube_import_url = ""
            self.show_add_track_menu = False
            self.show_youtube_import_form = False
            self._set_youtube_import_notice(
                "success",
                "YouTube import complete",
                f"Imported {display_name}",
                (
                    f"Source title: {video_title}\n"
                    f"Video ID: {video_id}\n"
                    f"Saved file: {display_name}\n\n"
                    "A new audio track was added to the track list."
                ),
                progress=100.0,
            )
            yield rx.toast.success("YouTube import complete.", duration=4000)
        except yt_dlp.utils.DownloadError as e:
            logging.exception(f"Error importing YouTube audio: {e}")
            friendly_error = _youtube_import_error_message(e)
            self._set_youtube_import_notice(
                "error",
                "YouTube import failed",
                friendly_error,
                f"{friendly_error}\n\nRaw error:\n{e}",
                friendly_error,
                progress=0.0,
            )
            self.youtube_import_notice_expanded = True
            yield rx.toast.error("YouTube import failed.", duration=5000)
        except Exception as e:
            logging.exception(f"Unexpected error importing YouTube audio: {e}")
            friendly_error = _youtube_import_error_message(e)
            self._set_youtube_import_notice(
                "error",
                "YouTube import failed",
                friendly_error,
                f"{friendly_error}\n\nRaw error:\n{e}",
                friendly_error,
                progress=0.0,
            )
            self.youtube_import_notice_expanded = True
            yield rx.toast.error("YouTube import failed.", duration=5000)
        finally:
            self.is_youtube_importing = False

    @rx.var
    def preview_data_json(self) -> str:
        return json.dumps({
            "tracks": self.audio_tracks,
            "segments": self.volume_segments,
            "duration": self.video_duration,
        })

    @rx.var
    def time_markers(self) -> list[dict[str, str | float]]:
        """Generate time ruler markers for the timeline."""
        if self.video_duration <= 0:
            return []
        # Choose interval based on duration
        dur = self.video_duration
        if dur <= 30:
            interval = 5
        elif dur <= 120:
            interval = 15
        elif dur <= 300:
            interval = 30
        else:
            interval = 60
        markers = []
        t = 0.0
        while t <= dur:
            mins = int(t) // 60
            secs = int(t) % 60
            label = f"{mins:02d}:{secs:02d}"
            pct = (t / dur) * 100 if dur > 0 else 0
            markers.append({"label": label, "pct": pct, "time": t})
            t += interval
        return markers

    @rx.var
    def selected_track_keyframes(self) -> list[dict[str, float]]:
        """Return keyframes for the currently selected track."""
        for track in self.audio_tracks:
            if track["id"] == self.selected_track_id:
                return track.get("volume_keyframes", [])
        return []

    @rx.var
    def audio_tracks_with_envelope(self) -> list[dict[str, Any]]:
        """Audio tracks enriched with SVG envelope visualization for timeline."""
        result = []
        for track in self.audio_tracks:
            enriched = dict(track)
            kfs = track.get("volume_keyframes", [])
            base_vol = float(track.get("volume", 1.0))
            trim_start = float(track.get("trim_start", 0.0))
            trim_end = float(track.get("trim_end", track.get("duration", 0.0)))
            dur = trim_end - trim_start
            if dur <= 0:
                enriched["env_bg_image"] = "none"
                result.append(enriched)
                continue

            # Sample at keyframe times + regular intervals for smooth curves
            sample_count = 80
            regular = [trim_start + (i / sample_count) * dur for i in range(sample_count + 1)]
            kf_times = [float(kf["time"]) for kf in kfs if trim_start <= float(kf["time"]) <= trim_end]
            times = sorted(set(regular + kf_times))

            eff_pts = []
            env_pts = []
            for t in times:
                x = ((t - trim_start) / dur) * 100
                env = _interpolate_envelope(kfs, t)
                eff = min(1.0, max(0.0, base_vol * env))
                eff_y = 100 - eff * 100
                eff_pts.append(f"{x:.1f},{eff_y:.1f}")
                env_disp = min(1.0, max(0.0, env))
                env_y = 100 - env_disp * 100
                env_pts.append(f"{x:.1f},{env_y:.1f}")

            x0 = ((times[0] - trim_start) / dur) * 100
            xn = ((times[-1] - trim_start) / dur) * 100
            fill_poly = f"{x0:.1f},100 " + " ".join(eff_pts) + f" {xn:.1f},100"
            eff_line = " ".join(eff_pts)
            env_line = " ".join(env_pts)

            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none">'
                f'<polygon points="{fill_poly}" fill="rgba(16,185,129,0.3)"/>'
                f'<polyline points="{eff_line}" fill="none" stroke="rgba(16,185,129,0.9)" '
                'stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
                f'<polyline points="{env_line}" fill="none" stroke="rgba(251,191,36,0.7)" '
                'stroke-width="1.5" stroke-dasharray="4,3" vector-effect="non-scaling-stroke"/>'
                '</svg>'
            )
            enriched["env_bg_image"] = f"url(\"data:image/svg+xml,{urllib.parse.quote(svg)}\")"
            result.append(enriched)
        return result

    @rx.event
    def preview_mix(self):
        if not self.video_file:
            return
        self.is_previewing = True

    @rx.event
    def stop_preview(self):
        self.is_previewing = False

    @rx.event
    def select_track(self, track_id: str):
        if self.selected_track_id == track_id:
            self.selected_track_id = ""
        else:
            self.selected_track_id = track_id

    @rx.event
    def remove_audio_track(self, track_id: str):
        self.audio_tracks = [t for t in self.audio_tracks if t["id"] != track_id]
        if self.selected_track_id == track_id:
            self.selected_track_id = ""

    @rx.event
    def duplicate_track(self, track_id: str):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                new_id = f"trk_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
                new_track = dict(track)
                new_track["id"] = new_id
                self.audio_tracks.append(new_track)
                break

    @rx.event
    def add_volume_segment(self, time: float):
        if not self.volume_segments:
            return
        new_segments = []
        inserted = False
        for seg in self.volume_segments:
            if not inserted and seg["start"] < time < seg["end"]:
                new_segments.append(
                    {"start": seg["start"], "end": time, "volume": seg["volume"]}
                )
                new_segments.append(
                    {"start": time, "end": seg["end"], "volume": seg["volume"]}
                )
                inserted = True
            else:
                new_segments.append(seg)
        if inserted:
            self.volume_segments = new_segments

    @rx.event
    def remove_volume_segment(self, index: int):
        if index < 0 or index >= len(self.volume_segments):
            return
        if len(self.volume_segments) <= 1:
            self.volume_segments[0]["start"] = 0.0
            self.volume_segments[0]["end"] = self.video_duration
            return
        segments = list(self.volume_segments)
        if index == len(segments) - 1:
            segments[index - 1]["end"] = segments[index]["end"]
        else:
            segments[index + 1]["start"] = segments[index]["start"]
        segments.pop(index)
        self.volume_segments = segments

    @rx.event
    def update_segment_volume(self, index: int, volume: float):
        if 0 <= index < len(self.volume_segments):
            self.volume_segments[index]["volume"] = max(0.0, min(2.0, float(volume)))

    @rx.event
    def update_track_start_time(self, track_id: str, time: float):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                track["start_time"] = float(time)
                break

    @rx.event
    def update_track_trim(self, track_id: str, trim_start: float, trim_end: float):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                trim_start = max(0.0, float(trim_start))
                trim_end = min(track["duration"], float(trim_end))
                if trim_start < trim_end:
                    track["trim_start"] = trim_start
                    track["trim_end"] = trim_end
                break

    @rx.event
    def update_track_trim_start(self, track_id: str, trim_start: float):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                trim_start = max(0.0, float(trim_start))
                trim_end = track.get("trim_end", track["duration"])
                if trim_start < trim_end:
                    track["trim_start"] = trim_start
                break

    @rx.event
    def update_track_trim_end(self, track_id: str, trim_end: float):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                trim_end = min(track["duration"], float(trim_end))
                trim_start = track.get("trim_start", 0.0)
                if trim_start < trim_end:
                    track["trim_end"] = trim_end
                break

    @rx.event
    def update_track_volume(self, track_id: str, volume: float):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                track["volume"] = max(0.0, min(2.0, float(volume)))
                break

    @rx.event
    def toggle_track_mute(self, track_id: str):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                track["muted"] = not track.get("muted", False)
                break

    @rx.event
    def toggle_track_solo(self, track_id: str):
        for track in self.audio_tracks:
            if track["id"] == track_id:
                track["solo"] = not track.get("solo", False)
                break

    # ── Volume Envelope (per-track keyframes) ──

    @rx.event
    def add_volume_keyframe(self, track_id: str, time: float, volume: float):
        """Add a keyframe to a track's volume envelope."""
        for track in self.audio_tracks:
            if track["id"] == track_id:
                kfs = list(track.get("volume_keyframes", []))
                time = round(float(time), 2)
                volume = max(0.0, min(2.0, float(volume)))
                # Replace if same time exists
                kfs = [k for k in kfs if abs(k["time"] - time) > 0.01]
                kfs.append({"time": time, "volume": volume})
                kfs.sort(key=lambda k: k["time"])
                track["volume_keyframes"] = kfs
                break

    @rx.event
    def remove_volume_keyframe(self, track_id: str, index: int):
        """Remove a keyframe by index from a track's volume envelope."""
        for track in self.audio_tracks:
            if track["id"] == track_id:
                kfs = list(track.get("volume_keyframes", []))
                if 0 <= int(index) < len(kfs):
                    kfs.pop(int(index))
                    track["volume_keyframes"] = kfs
                break

    @rx.event
    def update_volume_keyframe(self, track_id: str, index: int, time: float, volume: float):
        """Update an existing keyframe's time and volume."""
        for track in self.audio_tracks:
            if track["id"] == track_id:
                kfs = list(track.get("volume_keyframes", []))
                idx = int(index)
                if 0 <= idx < len(kfs):
                    kfs[idx] = {
                        "time": round(float(time), 2),
                        "volume": max(0.0, min(2.0, float(volume))),
                    }
                    kfs.sort(key=lambda k: k["time"])
                    track["volume_keyframes"] = kfs
                break

    @rx.event(background=True)
    async def export_video(self):
        async with self:
            if not self.video_file:
                self.export_error = "No video file uploaded."
                yield rx.toast("Error: No video file uploaded.", duration=3000)
                return
            self.is_exporting = True
            self.export_progress = 0.0
            self.export_error = ""
            self.exported_file = ""
            yield rx.toast("Starting export...", duration=3000)
        try:
            import asyncio
            import re
            import os
            from pathlib import Path

            upload_dir = rx.get_upload_dir()
            async with self:
                video_path = upload_dir / self.video_file
                out_filename = f"exported_{self.video_file}"
                out_path = upload_dir / out_filename
                has_solo = any((t.get("solo", False) for t in self.audio_tracks))
                active_tracks = [
                    t
                    for t in self.audio_tracks
                    if not has_solo
                    and (not t.get("muted", False))
                    or (has_solo and t.get("solo", False))
                ]
                inputs = ["-i", str(video_path)]
                for t in active_tracks:
                    inputs.extend(["-i", str(upload_dir / t["path"])])
                filter_complex = []
                vol_filters = []
                for seg in self.volume_segments:
                    start = seg["start"]
                    end = seg["end"]
                    vol = seg["volume"]
                    if vol != 1.0:
                        vol_filters.append(
                            f"volume={vol}:enable='between(t,{start},{end})'"
                        )
                if vol_filters:
                    filter_complex.append(f"[0:a]{','.join(vol_filters)}[v_audio];")
                    video_audio_label = "[v_audio]"
                else:
                    video_audio_label = "[0:a]"
                audio_labels = [video_audio_label]
                for i, t in enumerate(active_tracks):
                    idx = i + 1
                    trim_start = t.get("trim_start", 0.0)
                    trim_end = t.get("trim_end", t.get("duration", 0.0))
                    vol = t.get("volume", 1.0)
                    delay_ms = int(t.get("start_time", 0.0) * 1000)
                    keyframes = t.get("volume_keyframes", [])
                    track_filter = f"[{idx}:a]atrim=start={trim_start}:end={trim_end},asetpts=PTS-STARTPTS"
                    # Build volume filters from keyframes (linear interpolation)
                    if keyframes and len(keyframes) >= 2:
                        vol_parts = []
                        for ki in range(len(keyframes) - 1):
                            k0 = keyframes[ki]
                            k1 = keyframes[ki + 1]
                            t0, v0 = float(k0["time"]), float(k0["volume"])
                            t1, v1 = float(k1["time"]), float(k1["volume"])
                            if abs(v0 - v1) < 0.001:
                                # Constant volume segment
                                if abs(v0 - 1.0) > 0.001:
                                    vol_parts.append(
                                        f"volume={v0}:enable='between(t,{t0},{t1})'"
                                    )
                            else:
                                # Linear ramp: volume changes from v0 to v1
                                dur = t1 - t0
                                if dur > 0:
                                    # Use volume expression for linear interpolation
                                    vol_parts.append(
                                        f"volume='{v0}+({v1}-{v0})*(t-{t0})/({t1}-{t0})':eval=frame:enable='between(t,{t0},{t1})'"
                                    )
                        # Handle volume after the last keyframe
                        last_kf = keyframes[-1]
                        last_vol = float(last_kf["volume"])
                        last_time = float(last_kf["time"])
                        if abs(last_vol - 1.0) > 0.001:
                            vol_parts.append(
                                f"volume={last_vol}:enable='gte(t,{last_time})'"
                            )
                        # Handle volume before the first keyframe
                        first_kf = keyframes[0]
                        first_vol = float(first_kf["volume"])
                        first_time = float(first_kf["time"])
                        if first_time > 0 and abs(first_vol - 1.0) > 0.001:
                            vol_parts.append(
                                f"volume={first_vol}:enable='lt(t,{first_time})'"
                            )
                        if vol_parts:
                            track_filter += "," + ",".join(vol_parts)
                    elif vol != 1.0:
                        track_filter += f",volume={vol}"
                    if delay_ms > 0:
                        track_filter += f",adelay={delay_ms}|{delay_ms}"
                    label = f"[a_{idx}]"
                    track_filter += f"{label};"
                    filter_complex.append(track_filter)
                    audio_labels.append(label)
                if len(audio_labels) > 1:
                    mix_filter = (
                        "".join(audio_labels)
                        + f"amix=inputs={len(audio_labels)}:duration=first:dropout_transition=2[a_out]"
                    )
                    filter_complex.append(mix_filter)
                    map_audio = ("-map", "[a_out]")
                else:
                    map_audio = ("-map", video_audio_label.strip("[]"))
                cmd = ["ffmpeg", "-y", *inputs]
                if filter_complex:
                    cmd.extend(["-filter_complex", "".join(filter_complex)])
                    cmd.extend(["-map", "0:v"])
                    if len(audio_labels) > 1:
                        cmd.extend(["-map", "[a_out]"])
                    else:
                        cmd.extend(["-map", "0:a"])
                else:
                    cmd.extend(["-c", "copy"])
                cmd.extend(
                    ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_path)]
                )
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            time_regex = re.compile("time=(\\d+):(\\d+):(\\d+\\.\\d+)")
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace")
                match = time_regex.search(line_str)
                if match:
                    async with self:
                        if self.video_duration > 0:
                            h, m, s = match.groups()
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)
                            progress = min(
                                99.0, current_time / self.video_duration * 100
                            )
                            if progress - self.export_progress > 5.0:
                                self.export_progress = progress
                                yield
            await process.wait()
            async with self:
                if process.returncode == 0:
                    self.export_progress = 100.0
                    self.exported_file = out_filename
                    yield rx.toast("Export completed successfully!", duration=5000)
                else:
                    self.export_error = (
                        f"FFmpeg failed with exit code {process.returncode}"
                    )
                    yield rx.toast(f"Export failed: {self.export_error}", duration=5000)
        except Exception as e:
            async with self:
                self.export_error = str(e)
                logging.exception(f"Export error: {e}")
                yield rx.toast(f"Export error: {e}", duration=5000)
        finally:
            async with self:
                self.is_exporting = False