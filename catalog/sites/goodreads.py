import json
import logging
from datetime import datetime

from django.utils.timezone import make_aware
from lxml import html

from catalog.book.models import Edition, Work
from catalog.book.utils import binding_to_format, detect_isbn_asin
from catalog.common import *
from common.models.lang import detect_language
from journal.models.renderers import html_to_text

_logger = logging.getLogger(__name__)


class GoodreadsDownloader(RetryDownloader):
    def validate_response(self, response):
        if response is None:
            return RESPONSE_NETWORK_ERROR
        elif response.status_code == 200:
            if (
                response.text.find("__NEXT_DATA__") != -1
                and response.text.find('"title"') != -1
            ):
                return RESPONSE_OK
            # Goodreads may return legacy version for a/b testing
            # retry if so
            return RESPONSE_NETWORK_ERROR
        else:
            return RESPONSE_INVALID_CONTENT


@SiteManager.register
class Goodreads(AbstractSite):
    SITE_NAME = SiteName.Goodreads
    ID_TYPE = IdType.Goodreads
    WIKI_PROPERTY_ID = "P2968"
    DEFAULT_MODEL = Edition
    URL_PATTERNS = [
        r".+goodreads\.com/.*book/show/(\d+)",
        r".+goodreads\.com/.*book/(\d+)",
    ]

    @classmethod
    def id_to_url(cls, id_value):
        return "https://www.goodreads.com/book/show/" + id_value

    def scrape(self, response=None):
        data = {}
        if response is not None:
            h = html.fromstring(response.text.strip())
        else:
            dl = GoodreadsDownloader(self.url)
            h = dl.download().html()
        # Next.JS version of GoodReads
        # JSON.parse(document.getElementById('__NEXT_DATA__').innerHTML)['props']['pageProps']['apolloState']
        src = self.query_str(h, '//script[@id="__NEXT_DATA__"]/text()')
        if not src:
            raise ParseError(self, "__NEXT_DATA__ element")
        d = json.loads(src)["props"]["pageProps"]["apolloState"]
        o = {"Book": [], "Work": [], "Series": [], "Contributor": []}
        for v in d.values():
            t = v.get("__typename")
            if t and t in o:
                o[t].append(v)
        b = next(filter(lambda x: x.get("title"), o["Book"]), None)
        if not b:
            # Goodreads may return empty page template when internal service timeouts
            raise ParseError(self, "Book in __NEXT_DATA__ json")
        data["title"] = b["title"]
        data["brief"] = html_to_text(b["description"] or "").strip()
        lang = detect_language(b["title"] + " " + data["brief"])
        data["localized_title"] = [{"lang": lang, "text": b["title"]}]
        data["localized_subtitle"] = []  # Goodreads does not support subtitle
        if data["brief"]:
            data["brief"] = html_to_text(data["brief"])
        data["localized_description"] = (
            [{"lang": lang, "text": data["brief"]}] if data["brief"] else []
        )
        data["author"] = [c["name"] for c in o["Contributor"] if c.get("name")]
        ids = {}
        t, n = detect_isbn_asin(b["details"].get("asin"))
        if t:
            ids[t] = n
        # amazon has a known problem to use another book's isbn as asin
        # so we alway overwrite asin-converted isbn with real isbn
        t, n = detect_isbn_asin(b["details"].get("isbn13"))
        if t:
            ids[t] = n
        else:
            t, n = detect_isbn_asin(b["details"].get("isbn"))
            if t:
                ids[t] = n
        data["pages"] = b["details"].get("numPages")
        data["binding"] = b["details"].get("format")
        data["format"] = binding_to_format(b["details"].get("format"))
        data["pub_house"] = b["details"].get("publisher")
        if b["details"].get("publicationTime"):
            dt = make_aware(
                datetime.fromtimestamp(b["details"].get("publicationTime") / 1000)
            )
            data["pub_year"] = dt.year
            data["pub_month"] = dt.month
        if b["details"].get("language", {}).get("name"):
            data["language"] = [b["details"].get("language").get("name")]
        data["cover_image_url"] = b["imageUrl"]
        w = next(filter(lambda x: x.get("details"), o["Work"]), None)
        if w:
            data["required_resources"] = [
                {
                    "model": "Work",
                    "id_type": IdType.Goodreads_Work,
                    "id_value": str(w["legacyId"]),
                    "title": w["details"]["originalTitle"],
                    "url": w["editions"]["webUrl"],
                }
            ]
        pd = ResourceContent(metadata=data)
        pd.lookup_ids[IdType.ISBN] = ids.get(IdType.ISBN)
        pd.lookup_ids[IdType.ASIN] = ids.get(IdType.ASIN)
        return pd


@SiteManager.register
class Goodreads_Work(AbstractSite):
    SITE_NAME = SiteName.Goodreads
    ID_TYPE = IdType.Goodreads_Work
    WIKI_PROPERTY_ID = ""
    DEFAULT_MODEL = Work
    URL_PATTERNS = [r".+goodreads\.com/work/editions/(\d+)"]

    @classmethod
    def id_to_url(cls, id_value):
        return "https://www.goodreads.com/work/editions/" + id_value

    def scrape(self, response=None):
        content = BasicDownloader(self.url).download().html()
        title = self.query_str(content, "//h1/a/text()")
        if not title:
            raise ParseError(self, "title")
        author = self.query_str(content, "//h2/a/text()")
        try:
            first_published = self.query_str(content, "//h2/span/text()")
        except Exception:
            first_published = None
        pd = ResourceContent(
            metadata={
                "title": title,
                "localized_title": [{"lang": "en", "text": title}],
                "author": [author] if author else [],
                "first_published": first_published,
            }
        )
        return pd
