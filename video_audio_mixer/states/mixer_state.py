import reflex as rx
import subprocess
import json
import random
import string
import logging
from typing import Any


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


class MixerState(rx.State):
    video_file: str = ""
    video_filename: str = ""
    video_duration: float = 0.0
    video_size: str = ""
    audio_tracks: list[dict[str, Any]] = []
    volume_segments: list[dict[str, float]] = []
    selected_track_id: str = ""
    is_uploading: bool = False
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
                full_path = str(file_path.absolute())
                duration = get_media_duration(full_path)
                track_id = f"trk_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
                self.audio_tracks.append(
                    {
                        "id": track_id,
                        "filename": file.filename,
                        "path": unique_name,
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
                )
        except Exception as e:
            logging.exception(f"Error handling audio upload: {e}")
        finally:
            self.is_uploading = False

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