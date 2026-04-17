# Video Audio Mixer App

## Phase 1: Core UI Layout & Video/Audio Upload ✅
- [x] Build main app layout with header, sidebar for audio tracks, and central timeline/preview area
- [x] Implement video file upload with preview player
- [x] Implement audio file upload (multiple files supported) with track listing
- [x] Create basic state management for video/audio files and metadata

## Phase 2: Timeline Mixer Interface & Volume Controls ✅
- [x] Build visual timeline interface showing video track and audio tracks with time markers
- [x] Implement volume envelope controls (segment-based volume adjustment) for the video's own audio
- [x] Allow users to set start_time/end_time for imported audio tracks on the timeline
- [x] Add per-track volume sliders, mute/solo toggle functionality
- [x] Implement preview playback functionality with mixed audio preview

## Phase 3: Audio Mixing & Video Export ✅
- [x] Implement server-side audio mixing using ffmpeg (combine video audio with imported tracks)
- [x] Apply volume envelope/segment adjustments during mix
- [x] Generate final mixed video file for download
- [x] Add export progress indicator and download button
