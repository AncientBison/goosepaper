from typing import List
import pandas as pd
import datetime
import abc
import enum
import re

import twint

import bs4
import feedparser
import requests

from .styles import Style, AutumnStyle


def htmlize(text: str) -> str:
    """
    Generate HTML text from a text string, correctly formatting paragraphs etc.
    """
    # TODO:
    #   * Escaping
    #   * Paragraph delims
    #   * Remove illegal elements
    if isinstance(text, list):
        return "".join([f"<p>{line}</p>" for line in text])
    return f"<p>{text}</p>"


def clean_html(html: str) -> str:
    html = html.replace("â€TM", "'")
    html = re.sub(r"http[s]?:\/\/[^\s\"']+", "", html)
    return html


def clean_text(text: str) -> str:
    text = text.replace("â€TM", "'")
    text = re.sub(r"http[s]?:\/\/[^\s\"']+", "", text)
    return text


class PlacementPreference(enum.Enum):
    NONE = 0
    FULLPAGE = 1
    SIDEBAR = 2
    EAR = 3
    FOLIO = 4
    BANNER = 5


class StoryPriority(enum.Enum):
    DEFAULT = 0
    LOW = 1
    HEADLINE = 5
    BANNER = 9


class Story:
    def __init__(
        self,
        headline: str,
        body_html: str = None,
        body_text: str = None,
        byline: str = None,
        date: datetime.datetime = None,
        priority: int = StoryPriority.DEFAULT,
        placement_preference: PlacementPreference = PlacementPreference.NONE,
    ) -> None:
        """
        Create a new Story with headline and body text.
        """
        self.headline = headline
        self.priority = priority
        self.byline = byline
        self.date = date
        self.body_html = body_html if body_html else htmlize(body_text)
        self.placement_preference = placement_preference

    def to_html(self):
        byline_h4 = f"<h4 class='byline'>{self.byline}</h4>" if self.byline else ""
        priority_class = {
            StoryPriority.DEFAULT: "",
            StoryPriority.LOW: "priority-low",
            StoryPriority.BANNER: "priority-banner",
        }[self.priority]
        headline = (
            f"<h1 class='{priority_class}'>{self.headline}</h1>"
            if self.headline
            else ""
        )
        return f"""
        <article>
            {headline}
            {byline_h4}
            {self.body_html}
        </article>
        """


class StoryProvider(abc.ABC):
    """
    An abstract class for a class that provides stories to be rendered.
    """

    def get_stories(self, limit: int = 5):
        """
        Get a list of stories from this Provider.
        """
        ...


class WikipediaCurrentEventsStoryProvider(StoryProvider):
    """
    A story provider that reads from today's current events on Wikipedia.
    """

    def __init__(self):
        pass

    def get_stories(self, limit: int = 10) -> List[Story]:
        """
        Get a list of current stories from Wikipedia.
        """
        feed = feedparser.parse("https://www.to-rss.xyz/wikipedia/current_events/")
        # title = feed.entries[0].title
        title = "Today's Current Events"
        content = bs4.BeautifulSoup(feed.entries[0].summary, "lxml")
        for a in content.find_all("a"):
            while a.find("li"):
                a.find("li").replace_with_children()
            while a.find("ul"):
                a.find("ul").replace_with_children()
            a.replace_with_children()

        while content.find("dl"):
            content.find("dl").name = "h3"
        return [
            Story(
                headline=title,
                body_html=str(content),
                byline="Wikipedia Current Events",
                placement_preference=PlacementPreference.BANNER,
            )
        ]


class TwitterStoryProviderPriorityMode(enum.Enum):
    DEFAULT = 0
    RECENT = 1
    TOP = 2
    RATIO = 3


class TwitterStoryProvider(StoryProvider):
    def __init__(
        self,
        username: str,
        limit: int = 5,
        priority_mode: TwitterStoryProviderPriorityMode = TwitterStoryProviderPriorityMode.DEFAULT,
    ) -> None:
        """
        Create a new TwitterStoryProvider that reads from a username.

        Prioritizes stories based upon the TwitterStoryProviderPriorityMode.
        """
        self.username = username
        self.limit = limit
        self.priority_mode = priority_mode

    def get_stories(self, limit: int = 10) -> List[Story]:
        """
        Get a list of stories.

        Here, the headline is the @username, and the body text is the tweet.
        """

        c = twint.Config()
        c.Pandas = True
        c.Username = self.username
        c.Limit = min(self.limit, limit)
        c.Hide_output = True

        twint.run.Search(c)
        df = twint.storage.panda.Tweets_df
        return [
            Story(
                headline=None,
                body_text=clean_text(row.tweet),
                byline=f"@{self.username} on Twitter at {pd.to_datetime(row.date).strftime('%I:%M %p')}",
                date=pd.to_datetime(row.date),
                placement_preference=PlacementPreference.SIDEBAR,
            )
            for i, row in list(df.iterrows())[: min(self.limit, limit)]
        ]


class MultiTwitterStoryProvider(StoryProvider):
    def __init__(
        self,
        usernames: List[str],
        limit_per: int = 5,
        priority_mode: TwitterStoryProviderPriorityMode = TwitterStoryProviderPriorityMode.DEFAULT,
    ) -> None:
        """
        Create a new story provider that reads tweets from several users.

        Arguments:
            usernames (List[str]): A list of twitter usernames
            limit_per (int: 5): A maximum number of tweets to fetch from each
                user in `usernames`
            priority_mode (TwitterStoryProviderPriorityMode): Which priority
                technique to use. Not currently implemented.

        """
        self.usernames = usernames
        self.limit_per = limit_per
        self.priority_mode = priority_mode

    def get_stories(self, limit: int = 42) -> List[Story]:
        """
        Get a list of tweets where each tweet is a story.

        Arguments:
            limit (int: 15): The maximum number of tweets to fetch

        Returns:
            List[Story]: A list of tweets

        """
        stories = []
        for username in self.usernames:
            stories.extend(
                TwitterStoryProvider(
                    username, self.limit_per, self.priority_mode
                ).get_stories(limit=self.limit_per)
            )
        stories = sorted(stories, key=lambda story: story.date)
        return stories[:limit]


class LoremStoryProvider(StoryProvider):
    def __init__(self):
        self.text = [
            "Lorem ipsum! dolor sit amet, consectetur adipiscing elit. Duis eget velit sem. In elementum eget lorem non luctus. Vivamus tempus justo in pulvinar ultrices. Aliquam ac maximus leo. Quisque ipsum sapien, vestibulum viverra tempus ac, vestibulum quis justo. Nullam ut purus varius, bibendum metus ac, viverra enim. Phasellus sodales ullamcorper sapien pretium tristique. Duis dapibus felis quis tincidunt ultrices. Etiam purus sapien, tincidunt ac turpis vel, eleifend placerat enim. In sed mauris justo. Suspendisse ac tincidunt nunc. Nullam luctus porta pretium. Donec porttitor, nulla ut finibus pretium, augue turpis posuere ante, ac congue nunc nulla eu nisl. Phasellus imperdiet vel augue id gravida.",
            "Morbi mattis egestas quam, in tempus elit efficitur sagittis. Sed in maximus lorem. Aliquam erat volutpat. Phasellus mattis varius velit, vitae varius justo. Sed imperdiet eget dolor non consequat. Cras non felis neque. Nam eget arcu sapien. Morbi ultrices tristique cursus. Sed tempor ex lorem, vel ultrices sem placerat non. Nullam tortor arcu, imperdiet id lobortis a, commodo nec mi. Duis rhoncus in est sit amet tristique. Mauris condimentum nisl a erat tristique, id dictum risus euismod. Phasellus at sapien ante. Morbi facilisis tortor id leo porta, condimentum mollis dolor suscipit.",
            "Phasellus ut nibh vitae turpis congue venenatis. Morbi mollis justo dolor, ac finibus erat suscipit vitae. Donec libero erat, luctus quis sapien vel, sagittis dapibus est. Ut non quam et nisl hendrerit sodales. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Integer sodales ut augue a lacinia. Phasellus mattis sapien eget nibh auctor porttitor. Sed feugiat consectetur risus, a tempus ipsum scelerisque eu. Maecenas suscipit erat quis neque vulputate, ornare vehicula tellus lobortis. Duis tempor elit scelerisque ex tincidunt imperdiet. Curabitur dictum condimentum turpis, vitae ultrices ante sodales a. Praesent eu erat nec odio placerat placerat. Sed et dolor augue.",
            "Curabitur consectetur, nisi eget consequat ultrices, erat ante tincidunt ipsum, eget varius mauris turpis ac enim. Vivamus rutrum condimentum metus ut egestas. Nulla consectetur tincidunt laoreet. Vivamus tortor sem, imperdiet sodales facilisis quis, elementum nec erat. Curabitur imperdiet, nulla vel mattis gravida, risus eros sollicitudin magna, nec feugiat mauris mauris eu lorem. In hac habitasse platea dictumst. Sed tincidunt facilisis sem, non commodo metus volutpat nec. Fusce nulla mauris, vulputate sit amet magna id, blandit ornare leo. Nam vel faucibus ipsum, ac congue dolor.",
            "Vivamus pretium purus vel libero finibus blandit. Donec vitae nisl sollicitudin, consectetur nunc ac, volutpat libero. Maecenas ac leo ut velit viverra aliquet non id turpis. Morbi ut euismod erat. Vestibulum congue sed erat nec dapibus. Donec semper consectetur vestibulum. Praesent egestas dolor a ante sodales maximus. Suspendisse a odio vitae odio sagittis sollicitudin in quis massa. Praesent at convallis nulla. Mauris a nisl tincidunt, iaculis lacus eget, lobortis sapien. Nullam condimentum neque quis nisi consequat, eget accumsan tellus fermentum. Quisque dictum, nunc et pretium accumsan, lacus eros pharetra odio, ac euismod orci lorem sed turpis. ",
        ]

    def get_stories(self, limit: int = 5) -> List[Story]:
        return [
            Story(headline="Lorem Ipsum Dolor Sit Amet", body_text=self.text)
            for _ in range(limit)
        ]


class WeatherStoryProvider(StoryProvider):
    def __init__(self, woe: str = "2358820", F: bool = True):
        self.woe = woe
        self.F = F

    def CtoF(self, temp: float) -> float:
        return (temp * 9/5) + 32

    def get_stories(self, limit: int = 1) -> List[Story]:
        weatherReq = requests.get(
            f"https://www.metaweather.com/api/location/{self.woe}/"
        ).json()
        weather = weatherReq["consolidated_weather"][0]
        weatherTitle = weatherReq["title"]
        if self.F:
            headline = f"{int(self.CtoF(weather['the_temp']))}ºF with {weather['weather_state_name']} in {weatherTitle}"
            body_html = f"""
            <img
                src="https://www.metaweather.com/static/img/weather/png/64/{weather['weather_state_abbr']}.png"
                width="42" />
            {int(self.CtoF(weather['min_temp']))} – {int(self.CtoF(weather['max_temp']))}ºF, Winds {weather['wind_direction_compass']}
            """
        else:
            headline = f"{weather['the_temp']:.1f}ºC with {weather['weather_state_name']} in {weatherTitle}"
            body_html = f"""
            <img
                src="https://www.metaweather.com/static/img/weather/png/64/{weather['weather_state_abbr']}.png"
                width="42" />
            {weather['min_temp']:.1f} – {weather['max_temp']:.1f}ºC, Winds {weather['wind_direction_compass']}
            """
        return [
            Story(
                headline=headline,
                body_html=body_html,
                placement_preference=PlacementPreference.EAR,
            )
        ]


class RSSFeedStoryProvider(StoryProvider):
    def __init__(self, rss_path: str, limit: int = 5) -> None:
        self.limit = limit
        self.feed_url = rss_path

    def get_stories(self, limit: int = 5) -> List[Story]:
        feed = feedparser.parse(self.feed_url)
        limit = min(self.limit, len(feed.entries))
        stories = []
        for entry in feed.entries[:limit]:
            if "content" in entry:
                html = entry.content[0]["value"]
            elif "summary_detail" in entry:
                html = entry.summary_detail["value"]
            else:
                html = entry.summary
            html = clean_html(html)
            try:
                if len(entry.media_content):
                    src = entry.media_content[0]["url"]
                    html = f"<figure><img class='hero-img' src='{src}' /></figure>'" + html
            except Exception:
                pass

            stories.append(Story(entry.title, body_html=html))
        return stories


class RedditHeadlineStoryProvider(StoryProvider):
    def __init__(self, subreddit: str, limit: int = 20):
        self.limit = limit
        subreddit.lstrip("/")
        subreddit = subreddit[2:] if subreddit.startswith("r/") else subreddit
        self.subreddit = subreddit

    def get_stories(self, limit: int = 20) -> List[Story]:
        feed = feedparser.parse(f"https://www.reddit.com/r/{self.subreddit}.rss")
        limit = min(self.limit, len(feed.entries), limit)
        stories = []
        for entry in feed.entries[:limit]:
            try:
                author = entry.author
            except AttributeError:
                author = "A Reddit user"
            stories.append(
                Story(
                    headline=None,
                    body_text=entry.title,
                    byline=f"{author} in r/{self.subreddit}",
                    date=entry.updated_parsed,
                    placement_preference=PlacementPreference.SIDEBAR,
                )
            )
        return stories


class Goosepaper:
    def __init__(
        self,
        story_providers: List[StoryProvider],
        title: str = None,
        subtitle: str = None,
    ):
        self.story_providers = story_providers
        self.title = title if title else "Daily Goosepaper"
        self.subtitle = (
            subtitle if subtitle else datetime.datetime.today().strftime("%B %d, %Y")
        )

    def to_html(self) -> str:
        stories = []
        for prov in self.story_providers:
            stories.extend(prov.get_stories())

        # Get ears:
        ears = [s for s in stories if s.placement_preference == PlacementPreference.EAR]
        right_ear = ""
        left_ear = ""
        if len(ears) > 0:
            right_ear = ears[0].to_html()
        if len(ears) > 1:
            left_ear = ears[1].to_html()

        main_stories = [
            s.to_html()
            for s in stories
            if s.placement_preference
            not in [PlacementPreference.EAR, PlacementPreference.SIDEBAR]
        ]

        sidebar_stories = [
            s.to_html()
            for s in stories
            if s.placement_preference == PlacementPreference.SIDEBAR
        ]

        return f"""
            <html>
            <head>
                <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
                <meta charset="UTF-8" />
            </head>
            <body>
                <div class="header">
                    <div class="left-ear ear">{left_ear}</div>
                    <div><h1>{self.title}</h1><h4>{self.subtitle}</h4></div>
                    <div class="right-ear ear">{right_ear}</div>
                </div>
                <div class="stories row">
                    <div class="main-stories column">
                        {"<hr />".join(main_stories)}
                    </div>
                    <div class="sidebar column">
                        {"<br />".join(sidebar_stories)}
                    </div>
                </div>
            </body>
            </html>
        """

    def to_pdf(self, filename: str, style: Style = AutumnStyle) -> str:
        """
        Renders the current Goosepaper to a PDF file on disk.

        TODO: If an IO type is provided, write bytes instead.

        """
        from weasyprint import HTML, CSS

        style = style()

        html = self.to_html()
        h = HTML(string=html)
        c = CSS(string=style.get_css())
        h.write_pdf(filename, stylesheets=[c, *style.get_stylesheets()])
        return filename


def transfer_file_to_remarkable(fname: str, config_dict: dict = None):
    from rmapy.document import ZipDocument
    from rmapy.api import Client

    rm = Client(config_dict=config_dict)
    rm.renew_token()
    doc = ZipDocument(doc=fname)
    rm.upload(doc)
    return True
