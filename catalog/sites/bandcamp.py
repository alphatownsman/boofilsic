from catalog.common import *
from catalog.models import *
import logging
import urllib.parse
import dateparser
import re
import json


_logger = logging.getLogger(__name__)


@SiteManager.register
class Bandcamp(AbstractSite):
    SITE_NAME = SiteName.Bandcamp
    ID_TYPE = IdType.Bandcamp
    URL_PATTERNS = [r"https://([a-z0-9\-]+.bandcamp.com/album/[^?#/]+).*"]
    URL_PATTERN_FALLBACK = r"https://([a-z0-9\-\.]+/album/[^?#/]+).*"
    WIKI_PROPERTY_ID = ""
    DEFAULT_MODEL = Album

    @classmethod
    def id_to_url(cls, id_value):
        return f"https://{id_value}"

    @classmethod
    def validate_url_fallback(cls, url):
        if re.match(cls.URL_PATTERN_FALLBACK, url) is None:
            return False
        parsed_url = urllib.parse.urlparse(url)
        hostname = parsed_url.netloc
        try:
            answers = dns.resolver.query(hostname, "CNAME")
            for rdata in answers:
                if str(rdata.target) == "dom.bandcamp.com.":
                    return True
        except Exception:
            pass
        try:
            answers = dns.resolver.query(hostname, "A")
            for rdata in answers:
                if str(rdata.address) == "35.241.62.186":
                    return True
        except Exception:
            pass

    def scrape(self):
        content = BasicDownloader(self.url).download().html()
        try:
            title = content.xpath("//h2[@class='trackTitle']/text()")[0].strip()
            artist = [
                content.xpath("//div[@id='name-section']/h3/span/a/text()")[0].strip()
            ]
        except IndexError:
            raise ValueError("given url contains no valid info")

        genre = []  # TODO: parse tags
        track_list = ""
        release_nodes = content.xpath(
            "//div[@class='tralbumData tralbum-credits']/text()"
        )
        release_date = (
            dateparser.parse(
                re.sub(r"releas\w+ ", "", release_nodes[0].strip())
            ).strftime("%Y-%m-%d")
            if release_nodes
            else None
        )
        duration = None
        company = None
        brief_nodes = content.xpath("//div[@class='tralbumData tralbum-about']/text()")
        brief = "".join(brief_nodes) if brief_nodes else None
        cover_url = content.xpath("//div[@id='tralbumArt']/a/@href")[0].strip()
        bandcamp_page_data = json.loads(
            content.xpath("//meta[@name='bc-page-properties']/@content")[0].strip()
        )
        bandcamp_album_id = bandcamp_page_data["item_id"]

        data = {
            "title": title,
            "artist": artist,
            "genre": genre,
            "track_list": track_list,
            "release_date": release_date,
            "duration": duration,
            "company": company,
            "brief": brief,
            "bandcamp_album_id": bandcamp_album_id,
            "cover_image_url": cover_url,
        }
        pd = ResourceContent(metadata=data)
        if data["cover_image_url"]:
            imgdl = BasicImageDownloader(data["cover_image_url"], self.url)
            try:
                pd.cover_image = imgdl.download().content
                pd.cover_image_extention = imgdl.extention
            except Exception:
                _logger.debug(
                    f'failed to download cover for {self.url} from {data["cover_image_url"]}'
                )
        return pd
