"""Static file storage for the live server."""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Compressed, fingerprinted static files that never crash a page.

    The strict version raises "Missing staticfiles manifest entry" when a
    template asks for a path that is not a collected file. The Jazzmin admin
    theme does this on every signed-in admin page ({% static 'vendor/bootswatch' %}
    is a folder, used to build theme links), which turned /admin/ into a
    Server Error (500). Such paths are now served under their plain name, and
    every real file still gets its fingerprinted, long-cached name.
    """

    manifest_strict = False
