from max_float.service import app, page


def test_page_names_the_app():
    assert "<h1>max-float</h1>" in page()


def test_page_is_served_at_the_root():
    assert {route.path for route in app.routes} >= {"/"}
