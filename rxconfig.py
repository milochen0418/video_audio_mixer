import reflex as rx

config = rx.Config(
	app_name="video_audio_mixer",
	plugins=[rx.plugins.TailwindV3Plugin()],
	disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
