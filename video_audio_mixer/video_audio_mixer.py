import reflex as rx
from video_audio_mixer.components.header import header
from video_audio_mixer.components.panels import video_panel, audio_panel
from video_audio_mixer.components.timeline import timeline


def index() -> rx.Component:
    return rx.el.div(
        header(),
        rx.el.main(
            rx.el.div(
                video_panel(),
                audio_panel(),
                class_name="flex flex-col lg:flex-row gap-6 w-full",
            ),
            timeline(),
            class_name="flex-1 w-full max-w-screen-2xl mx-auto p-6 flex flex-col",
        ),
        class_name="min-h-screen bg-neutral-950 text-neutral-100 font-['Inter'] flex flex-col selection:bg-indigo-500/30",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/")