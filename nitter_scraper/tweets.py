from requests_html import HTMLSession, HTML
import re
from datetime import datetime
from nitter_scraper.schema import Tweet
from nitter_scraper.config import NITTER_URL


def link_parser(tweet_link):
    links = list(tweet_link.links)
    tweet_url = links[0]
    parts = links[0].split("/")

    tweet_id = parts[-1].replace("#m", "")
    username = parts[1]
    return tweet_id, username, tweet_url


def date_parser(tweet_date):
    split_datetime = tweet_date.split(",")

    day, month, year = split_datetime[0].strip().split("/")
    hours, minutes, seconds = split_datetime[1].strip().split(":")

    day = int(day)
    month = int(month)
    year = int(year)

    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)

    return datetime(year=year, month=month, day=day, hour=hours, minute=minutes, second=seconds)


def clean_stat(stat):
    return int(stat.replace(",", ""))


def stats_parser(tweet_stats):
    stats = {}
    for ic in tweet_stats.find(".icon-container"):
        key = ic.find("span", first=True).attrs["class"][0].replace("icon", "").replace("-", "")
        value = ic.text
        stats[key] = value
    return stats


def attachment_parser(attachements):
    photos, videos = [], []
    if attachements:
        photos = [i.attrs["src"] for i in attachements.find("img")]
        videos = [i.attrs["src"] for i in attachements.find("source")]
    return photos, videos


def cashtag_parser(text):
    cashtag_regex = re.compile(r"\$[^\d\s]\w*")
    return cashtag_regex.findall(text)


def hashtag_parser(text):
    hashtag_regex = re.compile(r"\#[^\d\s]\w*")
    return hashtag_regex.findall(text)


def url_parser(links):
    return list(filter(lambda link: "http://" in link or "https://" in link, links))


def parse_tweet(html):
    data = {}
    id, username, url = link_parser(html.find(".tweet-link", first=True))
    data["tweet_id"] = id
    data["tweet_url"] = url
    data["username"] = username

    retweet = html.find(".retweet-header .icon-container .icon-retweet", first=True)
    data["is_retweet"] = True if retweet else False

    body = html.find(".tweet-body", first=True)

    pinned = body.find(".pinned", first=True)
    data["is_pinned"] = True if pinned is not None else False

    data["time"] = date_parser(body.find(".tweet-date a", first=True).attrs["title"])

    content = body.find(".tweet-content", first=True)
    data["text"] = content.text

    # tweet_header = html.find(".tweet-header") #NOTE: Maybe useful later on

    stats = stats_parser(html.find(".tweet-stats", first=True))

    if stats.get("comment"):
        data["replies"] = clean_stat(stats.get("comment"))

    if stats.get("retweet"):
        data["retweets"] = clean_stat(stats.get("retweet"))

    if stats.get("heart"):
        data["likes"] = clean_stat(stats.get("heart"))

    entries = {}
    entries["hashtags"] = hashtag_parser(content.text)
    entries["cashtags"] = cashtag_parser(content.text)
    entries["urls"] = url_parser(content.links)

    photos, videos = attachment_parser(body.find(".attachments", first=True))
    entries["photos"] = photos
    entries["videos"] = videos

    data["entries"] = entries
    # quote = html.find(".quote", first=True) #NOTE: Maybe useful later on
    return Tweet.from_dict(data)


def get_tweets(query, pages=25, break_on_tweet_id: int = None):
    url = f"{NITTER_URL}/{query}"
    session = HTMLSession()

    def gen_tweets(pages):
        response = session.get(url)

        while pages > 0:
            if response.status_code == 200:
                html = HTML(html=response.text, default_encoding="utf-8")
                timeline = html.find(".timeline", first=True)

                next_page = list(timeline.find(".show-more")[-1].links)[0]
                next_url = f"{NITTER_URL}/{query}{next_page}"

                timeline_items = timeline.find(".timeline-item")

                for item in timeline_items:
                    if "show-more" in item.attrs["class"]:
                        continue

                    tweet = parse_tweet(item)

                    if tweet.tweet_id == break_on_tweet_id:
                        pages = 0
                        break

                    yield tweet

            response = session.get(next_url)
            pages -= 1

    yield from gen_tweets(pages)
