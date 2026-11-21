import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sightcall_qa_api.indexation.application.sitemap_crawler import SitemapCrawler
from sightcall_qa_api.indexation.domain.models.url import Url
from sightcall_qa_api.indexation.infrastructure.for_production.httpx_client import HTTPXClient

PRESS_RELEASE_SITEMAP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://sightcall.com/press-release/1</loc></url>
    <url><loc>https://sightcall.com/press-release/2</loc></url>
</urlset>"""


class _SitemapHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/press-release-sitemap.xml":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(PRESS_RELEASE_SITEMAP_XML)

    def log_message(self, *args):
        pass


@pytest.fixture
def server_url():
    # Local server: sightcall.com answers 403 to CI runners, so the test must not depend on it.
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SitemapHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


class TestSitemapCrawlerIntegration:
    def test_should_collect_links_from_press_release_sitemap(self, server_url):
        all_links = self._when_crawling_all_links(Url(f"{server_url}/press-release-sitemap.xml"))
        assert all_links == ["https://sightcall.com/press-release/1", "https://sightcall.com/press-release/2"]

    def test_should_fail_on_invalid_url(self, server_url):
        with pytest.raises(RuntimeError, match="404"):
            self._when_crawling_all_links(Url(f"{server_url}/this-sitemap-does-not-exist.xml"))

    def _when_crawling_all_links(self, root_url: Url) -> list[str]:
        crawler = SitemapCrawler(http_client=HTTPXClient())
        return crawler.run(root_url.value)["urls"]
