import curses, subprocess
from dateutil.parser import parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from imgii import image_to_ascii


class Window:
    border_height = 1
    border_width = 2

    def __init__(
        self, screen, height=None, width=None, max_lines=None, row_offset=0,
        col_offset=0, border=True, title=''
    ):
        # Size information.
        self.full_height = height if height is not None else curses.LINES
        self.full_width = width if width is not None else curses.COLS
        self.max_lines = max_lines      # This is a kludge.
        # TODO: We may need to figure out how to scroll the sidebar.

        # Position information.
        self.row_offset = row_offset
        self.col_offset = col_offset
        self.scroll_pos = 0

        # Size/offset may be defined relative to full size of terminal.
        if self.full_height < 0:
            self.full_height += curses.LINES
        if self.full_width < 0:
            self.full_width += curses.COLS
        if self.row_offset < 0:
            self.row_offset += curses.LINES
        if self.col_offset < 0:
            self.col_offset += curses.COLS

        # Curses setup.
        self.screen = screen
        self.window = curses.newwin(
            self.full_height, self.full_width, self.row_offset, self.col_offset
        )
        self.pad = curses.newpad(self.max_lines, self.width)

        # Border setup.
        if border:
            self.refresh_border()

        # Title setup.
        self.title = title
        if title:
            self.refresh_title()

    @property
    def height(self):
        return self.full_height - 2 * Window.border_height

    @property
    def width(self):
        return self.full_width - 2 * Window.border_width

    def write(self, string, row_offset=0, col_offset=0, attr=curses.A_NORMAL):
        try:
            self.pad.addstr(row_offset, col_offset, string, attr)
        except curses.error:
            # Lazy way to prevent writing too many buffer lines. Ugh.
            pass

    def scroll(self, scroll_pos):
        old_pos = self.scroll_pos
        self.scroll_pos = scroll_pos
        self.constrain_scroll()

        if self.scroll_pos != old_pos:
            self.refresh()

    def scroll_down(self, n=1):
        self.scroll(self.scroll_pos + n)

    def scroll_up(self, n=1):
        self.scroll(self.scroll_pos - n)

    def constrain_scroll(self, last_line=None):
        # Prevent negative scroll.
        self.scroll_pos = max(self.scroll_pos, 0)

        # Prevent scrolling past the content.
        if last_line is not None:
            self.scroll_pos = min(self.scroll_pos, last_line - self.height)

    def clear(self):
        self.pad.clear()

    def refresh(self):
        self.pad.noutrefresh(
            self.scroll_pos, 0,
            Window.border_height + self.row_offset,
            Window.border_width + self.col_offset,
            Window.border_height + self.row_offset + self.height - 1,
            Window.border_width + self.col_offset + self.width - 1
        )
        curses.doupdate()

    def refresh_border(self):
        self.window.border()
        self.window.noutrefresh()
        curses.doupdate()

    def refresh_title(self):
        self.window.addstr(0, centre(self.title, self.full_width), self.title)
        self.window.noutrefresh()
        curses.doupdate()

    def resize(self, height, width):
        # TODO
        pass


class Feed:
    def __init__(
        self, url, session, refresh_rate=10, timeout=None,
        browser='lynx'
    ):
        self.url = url
        self.main_url = ''
        self.title = url
        self.description = ''
        self.items = []

        self.session = session
        self.refresh_rate = timedelta(minutes=refresh_rate)
        self.timeout = timeout
        self.browser = browser

        self.last_refresh = None
        self.refresh(title_only=True)
        # TODO: This is just as slow as loading the whole thing. Use the DB.


    # TODO: Distinguish between load and refresh? When does stuff get loaded from DB?


    # Update object from web and write back to DB.
    def refresh(self, title_only=False, force=False):
        if not force and not self.needs_refresh:
            return

        xml = self.session.get(self.url, timeout=self.timeout).text
        soup = BeautifulSoup(xml, 'html.parser')

        self.title = soup.channel.title.string

        if title_only:
            return

        self.main_url = soup.channel.link.string
        self.description = soup.channel.description.string
        self.items = [
            Item(
                self.browser,
                item.title.string,
                item.link.string,
                parse(item.pubdate.string).astimezone(tz=None),
                item.guid.string,
                (item.find('content:encoded') or item.description).string
            )
            for item in soup.find_all('item')
        ]

        self.last_refresh = datetime.now()

        # TODO: Write back to DB.

    @property
    def needs_refresh(self):
        return (self.last_refresh is None) or (
            datetime.now() - self.last_refresh >= self.refresh_rate
        )


class Item:
    def __init__(self, browser, title, url, date, guid, content):
        self.browser = browser
        self.title = title
        self.url = url
        self.date = date
        self.guid = guid
        self.content = content

    def display_content(self, width):
        if self.browser == 'lynx':
            command = [
                'lynx', '-stdin', '-dump', '-width', str(width), '-image_links'
            ]
            encoding = 'iso-8859-1'
        elif browser == 'w3m':
            command = ['w3m', '-T', 'text/html', '-dump', '-cols', str(width)]
            encoding = 'utf-8'
        else:
            Exception('Unsuported browser: {}'.format(self.browser))

        output = subprocess.check_output(
            command,
            input=self.content.encode(encoding, 'xmlcharrefreplace'),
            stderr=subprocess.STDOUT
        )
        output = output.decode(encoding, 'xmlcharrefreplace')

        return output


def centre(text, width):
    return (width - len(text)) // 2
