"""Original hardened app, isolated state, unchanged controls, two Gunicorn threads."""
from app.server import create_app

app = create_app()


@app.after_request
def identify_capacity_lab(response):
    response.headers["X-V08-Lab"] = "two-worker-capacity-model"
    if response.mimetype == "text/html":
        response.set_data(response.get_data(as_text=True).replace(
            "<main>", '<main><div class="notice">Local V08 capacity lab: 2 workers; existing report quotas and cache enabled.</div>', 1))
    return response
