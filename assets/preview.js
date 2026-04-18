// Preview Mix: synchronize video playback with mixed audio tracks
window._previewActive = false;
window._audioElements = [];
window._previewTimers = [];
window._videoVolumeHandler = null;

// ── Timeline Playhead ──
(function initPlayhead() {
  var LABEL_WIDTH = 128; // w-32 = 8rem = 128px
  var _dragging = false;

  function getVideoDuration() {
    var el = document.getElementById("preview-data");
    if (el) {
      try { return JSON.parse(el.textContent || "{}").duration || 0; } catch(e) {}
    }
    var v = document.querySelector("video");
    return (v && v.duration && isFinite(v.duration)) ? v.duration : 0;
  }

  function pctFromEvent(e) {
    // Try tracks container first, fall back to ruler
    var container = document.getElementById("timeline-tracks") || document.getElementById("timeline-ruler");
    if (!container) return -1;
    var rect = container.getBoundingClientRect();
    var contentLeft = rect.left + LABEL_WIDTH;
    var contentWidth = rect.width - LABEL_WIDTH;
    if (contentWidth <= 0) return -1;
    return Math.max(0, Math.min(1, (e.clientX - contentLeft) / contentWidth));
  }

  function pctFromRulerEvent(e) {
    var ruler = document.getElementById("timeline-ruler");
    if (!ruler) return -1;
    var rect = ruler.getBoundingClientRect();
    var contentLeft = rect.left + LABEL_WIDTH;
    var contentWidth = rect.width - LABEL_WIDTH;
    if (contentWidth <= 0) return -1;
    return Math.max(0, Math.min(1, (e.clientX - contentLeft) / contentWidth));
  }

  function updatePlayhead() {
    var playhead = document.getElementById("timeline-playhead");
    var timeLabel = document.getElementById("timeline-current-time");
    if (!playhead) return;
    var video = document.querySelector("video");
    if (!video || !video.duration || !isFinite(video.duration)) {
      playhead.style.display = "none";
      return;
    }
    var dur = video.duration;
    var pct = (video.currentTime / dur) * 100;
    // Offset from the left edge of the tracks container, after the label column
    playhead.style.display = "block";
    playhead.style.left = "calc(" + LABEL_WIDTH + "px + " + pct + "% * (1 - " + LABEL_WIDTH + "px / 100%))";
    // Simpler: calculate pixel offset
    var container = document.getElementById("timeline-tracks");
    if (container) {
      var contentWidth = container.offsetWidth - LABEL_WIDTH;
      var px = LABEL_WIDTH + (pct / 100) * contentWidth;
      playhead.style.left = px + "px";
    }
    if (timeLabel) {
      var t = video.currentTime;
      var m = Math.floor(t / 60);
      var s = Math.floor(t % 60);
      var ms = Math.floor((t % 1) * 10);
      timeLabel.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s + "." + ms;
    }
  }

  // Listen for video timeupdate to move the playhead
  function attachVideoListener() {
    var video = document.querySelector("video");
    if (!video) return;
    if (video._playheadAttached) return;
    video._playheadAttached = true;
    video.addEventListener("timeupdate", updatePlayhead);
    video.addEventListener("seeked", updatePlayhead);
    video.addEventListener("loadedmetadata", updatePlayhead);
  }

  // Click on timeline tracks area → seek video
  window._timelineClick = function(e) {
    var pct = pctFromEvent(e);
    if (pct < 0) return;
    var dur = getVideoDuration();
    if (dur <= 0) return;
    var seekTime = pct * dur;
    var video = document.querySelector("video");
    if (video) {
      video.currentTime = seekTime;
      attachVideoListener();
      updatePlayhead();
    }
  };

  // Drag support on the playhead
  function onMouseDown(e) {
    if (pctFromEvent(e) < 0) return;
    _dragging = true;
    e.preventDefault();
  }
  function onMouseMove(e) {
    if (!_dragging) return;
    // Try both containers to get pct
    var pct = pctFromEvent(e);
    if (pct < 0) pct = pctFromRulerEvent(e);
    if (pct < 0) return;
    var dur = getVideoDuration();
    if (dur <= 0) return;
    var video = document.querySelector("video");
    if (video) {
      video.currentTime = pct * dur;
      updatePlayhead();
    }
  }
  function onMouseUp() {
    _dragging = false;
  }

  // Attach drag listeners after DOM is ready
  function setup() {
    var container = document.getElementById("timeline-tracks");
    if (container) {
      container.addEventListener("mousedown", onMouseDown);
    }
    var ruler = document.getElementById("timeline-ruler");
    if (ruler) {
      ruler.addEventListener("mousedown", onMouseDown);
    }
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    attachVideoListener();
    // Also re-attach when video element changes (Reflex re-renders)
    var observer = new MutationObserver(function() {
      attachVideoListener();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    // small delay to let Reflex render
    setTimeout(setup, 500);
  }
})();

// Entry point called directly from button click (preserves user gesture)
window.startPreviewFromDOM = function () {
  var el = document.getElementById("preview-data");
  if (!el) {
    console.error("[Preview] No #preview-data element found");
    return;
  }
  var raw = el.textContent || el.innerText || "";
  raw = raw.trim();
  if (!raw) {
    console.error("[Preview] #preview-data is empty");
    return;
  }
  try {
    var data = JSON.parse(raw);
    console.log("[Preview] Parsed data, tracks:", data.tracks.length);
  } catch (e) {
    console.error("[Preview] JSON parse failed:", e, "raw:", raw.substring(0, 100));
    return;
  }

  // Stop any previous preview
  window.stopPreview();
  window._previewActive = true;

  var video = document.querySelector("video");
  if (!video) {
    console.error("[Preview] No <video> element found");
    return;
  }

  console.log("[Preview] Starting playback...");
  // Start from the current video position (don't reset to 0)
  var videoStartTime = video.currentTime || 0;
  console.log("[Preview] Starting from time:", videoStartTime);
  video.muted = false;

  var segments = data.segments || [];

  // Volume segments for original video audio
  function updateVideoVolume() {
    if (!window._previewActive) return;
    var t = video.currentTime;
    var vol = 1.0;
    for (var i = 0; i < segments.length; i++) {
      if (t >= segments[i].start && t < segments[i].end) {
        vol = Math.min(1.0, segments[i].volume);
        break;
      }
    }
    video.volume = vol;
  }
  video.addEventListener("timeupdate", updateVideoVolume);
  window._videoVolumeHandler = updateVideoVolume;

  video.addEventListener("ended", function () {
    console.log("[Preview] Video ended");
    window.stopPreview();
  }, { once: true });

  // Play video immediately - must be synchronous in click handler
  video.play().then(function () {
    console.log("[Preview] Video playing OK");
  }).catch(function (err) {
    console.warn("[Preview] Video play error:", err.message);
  });

  // Determine which tracks should play
  var tracks = data.tracks || [];
  var hasSolo = tracks.some(function (t) { return t.solo; });

  // Derive the upload base URL from the video element's src
  // Video src is something like "http://localhost:8000/_upload/filename"
  var videoSrc = video.src || "";
  var uploadBase = "/_upload/";
  var uploadIdx = videoSrc.indexOf("/_upload/");
  if (uploadIdx !== -1) {
    uploadBase = videoSrc.substring(0, uploadIdx) + "/_upload/";
  }
  console.log("[Preview] Upload base URL:", uploadBase);

  tracks.forEach(function (track) {
    var shouldPlay = hasSolo ? track.solo : !track.muted;
    if (!shouldPlay) return;

      var audioUrl = uploadBase + encodeURIComponent(track.path);
    console.log("[Preview] Creating audio:", track.filename, "->", audioUrl);

    var audio = new Audio(audioUrl);
    audio.volume = Math.min(1.0, Math.max(0, track.volume || 1.0));
    window._audioElements.push(audio);

    var trimStart = track.trim_start || 0;
    var trimEnd = track.trim_end || track.duration || 9999;
    var startTime = track.start_time || 0;
    var keyframes = track.volume_keyframes || [];

    // Interpolate volume from keyframes at a given audio time
    function interpVolume(t) {
      if (keyframes.length === 0) return Math.min(1.0, Math.max(0, track.volume || 1.0));
      if (t <= keyframes[0].time) return Math.min(1.0, keyframes[0].volume);
      if (t >= keyframes[keyframes.length - 1].time) return Math.min(1.0, keyframes[keyframes.length - 1].volume);
      for (var j = 0; j < keyframes.length - 1; j++) {
        var k0 = keyframes[j], k1 = keyframes[j + 1];
        if (t >= k0.time && t <= k1.time) {
          var frac = (k1.time === k0.time) ? 0 : (t - k0.time) / (k1.time - k0.time);
          var vol = k0.volume + frac * (k1.volume - k0.volume);
          return Math.min(1.0, Math.max(0, vol));
        }
      }
      return Math.min(1.0, Math.max(0, track.volume || 1.0));
    }

    // Update volume based on keyframes during playback
    audio.addEventListener("timeupdate", function () {
      if (audio.currentTime >= trimEnd) {
        audio.pause();
        return;
      }
      audio.volume = interpVolume(audio.currentTime);
    });

    // KEY: Call play() synchronously here, inside the user click handler.
    // This "unlocks" the audio element for the browser autoplay policy.
    // Then we manage timing by pausing/seeking as needed.

    // Calculate where the audio should be relative to the video's current time
    var trackEnd = startTime + (trimEnd - trimStart);
    // If video is already past this track's end, skip it
    if (videoStartTime >= trackEnd) {
      console.log("[Preview] Skipping track (past end):", track.filename);
      return;
    }

    audio.play().then(function () {
      console.log("[Preview] Audio unlocked:", track.filename);
      if (videoStartTime >= startTime) {
        // Video is already within this track's range — seek audio to the right offset
        var audioOffset = trimStart + (videoStartTime - startTime);
        audio.currentTime = Math.min(audioOffset, trimEnd);
        audio.volume = interpVolume(audio.currentTime);
      } else {
        // Track hasn't started yet — pause and schedule for later
        audio.pause();
        audio.currentTime = trimStart;
        var delayMs = (startTime - videoStartTime) * 1000;
        var timer = setTimeout(function () {
          if (!window._previewActive) return;
          audio.play().catch(function (e) {
            console.warn("[Preview] Delayed play error:", e.message);
          });
        }, delayMs);
        window._previewTimers.push(timer);
      }
    }).catch(function (err) {
      console.warn("[Preview] Audio play error:", track.filename, err.message);
    });
  });
};

window.stopPreview = function () {
  console.log("[Preview] Stopping");
  window._previewActive = false;

  window._previewTimers.forEach(function (t) { clearTimeout(t); });
  window._previewTimers = [];

  var video = document.querySelector("video");
  if (video) {
    video.pause();
    // Don't reset currentTime — keep playhead at current position
    if (window._videoVolumeHandler) {
      video.removeEventListener("timeupdate", window._videoVolumeHandler);
      window._videoVolumeHandler = null;
    }
    video.volume = 1.0;
  }

  window._audioElements.forEach(function (a) {
    a.pause();
    a.src = "";
  });
  window._audioElements = [];
};
