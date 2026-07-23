from app.text import slugify


def test_slugify_trims_and_collapses_spaces():
    assert slugify("  Hello   World  ") == "hello-world"


def test_slugify_simple():
    assert slugify("Hello World") == "hello-world"
