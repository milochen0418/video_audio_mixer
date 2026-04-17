// Preview Mix: synchronize video playback with mixed audio tracks
window._previewActive = false;
window._audioElements = [];
window._previewTimers = [];
window._videoVolumeHandler = null;

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
  video.currentTime = 0;
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

    // Stop playback at trim end
    audio.addEventListener("timeupdate", function () {
      if (audio.currentTime >= trimEnd) {
        audio.pause();
      }
    });

    // KEY: Call play() synchronously here, inside the user click handler.
    // This "unlocks" the audio element for the browser autoplay policy.
    // Then we manage timing by pausing/seeking as needed.
    audio.play().then(function () {
      console.log("[Preview] Audio unlocked:", track.filename);
      if (startTime > 0) {
        // Needs delay: pause now, resume later at the right time
        audio.pause();
        audio.currentTime = trimStart;
        var timer = setTimeout(function () {
          if (!window._previewActive) return;
          audio.play().catch(function (e) {
            console.warn("[Preview] Delayed play error:", e.message);
          });
        }, startTime * 1000);
        window._previewTimers.push(timer);
      } else {
        // Play immediately from trim start
        if (trimStart > 0) {
          audio.currentTime = trimStart;
        }
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
    video.currentTime = 0;
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
