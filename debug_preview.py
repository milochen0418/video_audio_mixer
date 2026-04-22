"""Quick debug test: upload video + audio, click Preview, check console for errors."""
import asyncio
import os
import glob
from playwright.async_api import async_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000")

# Find test files from uploaded_files dir
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploaded_files")


def find_test_files():
    videos = glob.glob(os.path.join(UPLOAD_DIR, "*.mov")) + glob.glob(os.path.join(UPLOAD_DIR, "*.mp4"))
    audios = glob.glob(os.path.join(UPLOAD_DIR, "*.mp3")) + glob.glob(os.path.join(UPLOAD_DIR, "*.wav"))
    return videos[0] if videos else None, audios[0] if audios else None


async def main():
    video_file, audio_file = find_test_files()
    print(f"Video: {video_file}")
    print(f"Audio: {audio_file}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        context = await browser.new_context()
        page = await context.new_page()

        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))

        print(f"\n1) Navigating to {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Verify JS loaded
        fn_type = await page.evaluate("typeof window.startPreviewFromDOM")
        print(f"   startPreviewFromDOM: {fn_type}")
        assert fn_type == "function", "JS not loaded!"

        if not video_file or not audio_file:
            print("No test files found, skipping upload test")
            await browser.close()
            return

        # Upload video
        print(f"\n2) Uploading video...")
        video_drop = page.locator("text=Drag and drop a video file")
        async with page.expect_file_chooser() as fc_info:
            await video_drop.click()
        fc = await fc_info.value
        await fc.set_files(video_file)
        await page.wait_for_timeout(4000)

        # Verify video element appeared
        vid = await page.query_selector("video")
        print(f"   <video> found: {vid is not None}")

        # Upload audio
        print(f"\n3) Uploading audio...")
        add_btn = page.locator("text=Add Track")
        await add_btn.click()
        local_btn = page.locator("text=From Computer")
        await local_btn.wait_for(state="visible")
        async with page.expect_file_chooser() as fc_info:
            await local_btn.click()
        fc = await fc_info.value
        await fc.set_files(audio_file)
        await page.wait_for_timeout(4000)

        # Check preview data
        pd = await page.query_selector("#preview-data")
        pd_text = await pd.text_content() if pd else ""
        print(f"   #preview-data exists: {pd is not None}, length: {len(pd_text)}")
        if pd_text:
            import json
            data = json.loads(pd_text)
            print(f"   tracks: {len(data.get('tracks', []))}, duration: {data.get('duration')}")

        # Click Preview Mix
        print(f"\n4) Clicking Preview Mix...")
        preview_btn = page.locator("button:has-text('Preview Mix')")
        await preview_btn.click()
        await page.wait_for_timeout(5000)

        # Check video is playing
        is_paused = await page.evaluate("document.querySelector('video').paused")
        current_time = await page.evaluate("document.querySelector('video').currentTime")
        print(f"   Video paused: {is_paused}, currentTime: {current_time:.2f}")

        # Check audio elements
        audio_count = await page.evaluate("window._audioElements ? window._audioElements.length : 0")
        print(f"   Audio elements created: {audio_count}")

        if audio_count > 0:
            for i in range(audio_count):
                info = await page.evaluate(f"""(function() {{
                    var a = window._audioElements[{i}];
                    return {{
                        paused: a.paused,
                        currentTime: a.currentTime,
                        duration: a.duration,
                        readyState: a.readyState,
                        error: a.error ? a.error.message : null,
                        src: a.src,
                        networkState: a.networkState
                    }};
                }})()""")
                print(f"   Audio[{i}]: paused={info['paused']}, time={info['currentTime']:.2f}, "
                      f"readyState={info['readyState']}, networkState={info['networkState']}, "
                      f"error={info['error']}")

        # Print all console messages
        print(f"\n5) Console output ({len(console_msgs)} messages):")
        for msg in console_msgs:
            if "[Preview]" in msg or "error" in msg.lower() or "warn" in msg.lower():
                print(f"   {msg}")

        await browser.close()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
