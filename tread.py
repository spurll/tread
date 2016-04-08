#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, dateutil, textwrap, sys
from shutil import get_terminal_size
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil.parser import parse
from imgii import image_to_ascii


with open('config.yml') as f:
    config = yaml.load(f)

# Set up requests to fetch data with retries.
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=config.get('retries'))
session.mount('http://', adapter)


class Window:
    border_height = 1
    border_width = 2

    def __init__(
        self, screen,
        height=None, width=None, max_lines=None,
        row_offset=0, col_offset=0,
        border=True, title=''
    ):
        # Size information.
        self.full_height = height if height is not None else curses.LINES
        self.full_width = width if width is not None else curses.COLS
        self.max_lines = config.get('buffer_lines', 1000)   # This is a kludge.
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

    def print(self, string, row_offset=0, col_offset=0, attr=curses.A_NORMAL):
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
    refresh_rate = timedelta(minutes=config.get('refresh', 10))

    def __init__(self, url):
        self.url = url
        self.main_url = ''
        self.title = url
        self.description = ''
        self.items = []

        self.last_refresh = None
        self.refresh(title_only=True)
        # TODO: This is just as slow as loading the whole thing. Use the DB.


    # TODO: Distinguish between load and refresh? When does stuff get loaded from DB?


    # Update object from web and write back to DB.
    def refresh(self, title_only=False, force=False):
        if not force and not self.needs_refresh:
            return

        xml = session.get(self.url, timeout=config.get('timeout')).text
        soup = BeautifulSoup(xml, 'html.parser')

        self.title = soup.channel.title.string

        if title_only:
            return

        self.main_url = soup.channel.link.string
        self.description = soup.channel.description.string
        self.items = [
            Item(
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
            datetime.now() - self.last_refresh >= Feed.refresh_rate
        )


class Item:
    browser = config.get('browser', 'lynx')

    def __init__(self, title, url, date, guid, content):
        self.title = title
        self.url = url
        self.date = date
        self.guid = guid
        self.content = content

    def display_content(self, width):
        if Item.browser == 'lynx':
            command = [
                'lynx', '-stdin', '-dump', '-width', str(width), '-image_links'
            ]
            encoding = 'iso-8859-1'
        elif browser == 'w3m':
            command = ['w3m', '-T', 'text/html', '-dump', '-cols', str(width)]
            encoding = 'utf-8'
        else:
            Exception('Unsuported browser: {}'.format(Item.browser))

        output = subprocess.check_output(
            command,
            input=self.content.encode(encoding, 'xmlcharrefreplace'),
            stderr=subprocess.STDOUT
        )
        output = output.decode(encoding, 'xmlcharrefreplace')

        return output


def main(screen):
    # Ensure config['keys'] exists and make all keys uppercase.
    config['keys'] = configure_keys(config.get('keys', dict()))

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Turn off visible cursor.
    curses.curs_set(False)

    # Create screen objects.
    # TODO: Ensure screen is large enough to accommodate sidebar and content.
    content, sidebar, menu = init_windows(screen)

    # Add key listing to menu.
    menu.print(menu_text(config['keys'], menu.width))
    menu.refresh()

    # TODO
    # For each feed in config, load contents from the DB.
    # Mark all as "needs refresh".
    # Since the top one is selected, refresh it.
    # Proceed to display.


    # Fetch all feed data.
    feeds = [Feed(url) for url in config['feeds']]

    # Initial selections.
    if len(feeds) > 0:
        feeds[0].refresh()
    selected_feed = 0
    selected_item = 0


    # TODO: Feed selection, item selection, etc. should probably be abstracted
    # into an object as well. These loops are really awkward, as is the line-
    # counting.


    while True:
        current_item = None

        # Print sidebar.
        for i, feed in enumerate(feeds):
            sidebar.print(
                '{:{}}'.format(feed.title, sidebar.width),
                row_offset=i,
                attr=curses.A_REVERSE if i == selected_feed else curses.A_BOLD
            )

            if i == selected_feed:
                current_feed = feed

        # Refresh sidebar.
        sidebar.refresh()

        # Print content.
        line = 0
        for i, item in enumerate(current_feed.items):
            if line >= content.max_lines: break
            # TODO: This is a terrible kludge. At least warn or something.

            content.print(
                '{:{}}{:%Y-%m-%d %H:%M}'.format(
                    item.title, content.width - 16, item.date
                ),
                row_offset=line,
                attr=curses.A_REVERSE if i == selected_item else curses.A_BOLD
            )
            line += 1

            if i == selected_item:
                current_item = item
                line += 1

                # Parse the HTML content.
                parsed_string = item.display_content(content.width)

                # Print it to the screen.
                content.print(parsed_string, row_offset=line)

                line += parsed_string.count('\n') + 1

        # Undo scrolling if content isn't big enough to scroll.
        content.constrain_scroll(line)
        content.refresh()

        # Block, waiting for input.
        key = screen.getkey().upper()

        if key == config['keys']['next_item']:
            if len(current_feed.items) > 0:
                content.clear() # Should be more selective.
                selected_item = (selected_item + 1) % len(current_feed.items)
        elif key == config['keys']['prev_item']:
            if len(current_feed.items) > 0:
                content.clear() # Should be more selective.
                selected_item = (selected_item - 1) % len(current_feed.items)
        elif key == config['keys']['next_feed']:
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0
            feeds[selected_feed].refresh()
        elif key == config['keys']['prev_feed']:
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0
            feeds[selected_feed].refresh()
        elif key == config['keys']['scroll_down']:
            content.clear() # Should be more selective.
            content.scroll_down()
        elif key == config['keys']['scroll_up']:
            content.clear() # Should be more selective.
            content.scroll_up()
        elif key == config['keys']['open_in_browser']:
            if current_item is not None:
                open_in_browser(current_item.url)
        elif key == config['keys']['mark_read']:
            pass    # TODO
        elif key == config['keys']['mark_unread']:
            pass    # TODO
        elif key == config['keys']['star']:
            pass    # TODO
        elif key == config['keys']['quit']:
            break

        sidebar.refresh_border()
        sidebar.refresh_title()

    # Write a message function that pops up an overlay window to display a
    # message and pauses for anykey (or enter?)



    # Looks like some unicode characters aren't working:
    # http://xkcd.com/1647/



    # In the DB should store/use guids.
    # Should probably store all of the articles in the DB, and sync them with
    # feeds on launch and on demand.

    # Do something about resize!


    # Warn that this will probably only work in lynx (or implement both...?)
    # Insert output from image conversion on its own lines before the image tag
    # (leave it)
    # use image_to_ascii()

    # Also include html2text as a parser



def init_windows(screen):
    menu_items = 7
    menu_height = menu_items + 2 * Window.border_height

    content = Window(screen, width=-41, col_offset=41, title='TREAD')

    sidebar = Window(
        screen, width=40, height=-menu_height, max_lines=200,
        title='FEEDS'
    )

    menu = Window(
        screen, width=40, height=menu_height, row_offset=-menu_height,
        max_lines=menu_items, title='KEYS'
    )

    return (content, sidebar, menu)


def open_in_browser(url):
    if sys.platform.startswith('linux'):
        subprocess.Popen(['xdg-open', url])
    elif sys.platform.startswith('darwin'):
        subprocess.Popen(['open', url])


def centre(text, width):
    return (width - len(text)) // 2


def configure_keys(existing):
    default = {
        'prev_item': 'K',
        'next_item': 'J',
        'prev_feed': 'H',
        'next_feed': 'L',
        'scroll_up': 'KEY_UP',
        'scroll_down': 'KEY_DOWN',
        'mark_read': 'R',
        'mark_unread': 'U',
        'star': 'S',
        'open_in_browser': 'O',
        'quit': 'Q'
    }

    # Make uppercase.
    existing = {key: value.upper() for key, value in existing.items()}

    # Return default keys, overwriting with the keys that exist in config.
    return {**default, **existing}


def menu_text(keys, width):
    key_width = 17
    value_width = width - key_width
    menu_format = '{:<{}}{:>{}}'

    menu = [
        menu_format.format(
            'Prev/Next Item:', key_width,
            keys['prev_item'] + '/' + keys['next_item'], value_width
        ),
        menu_format.format(
            'Prev/Next Feed:', key_width,
            keys['prev_feed'] + '/' + keys['next_feed'], value_width
        ),
        menu_format.format(
            'Scroll Up/Down:', key_width,
            keys['scroll_up'] + '/' + keys['scroll_down'], value_width
        ),
        menu_format.format(
            'Mark Read/Unread:', key_width,
            keys['mark_read'] + '/' + keys['mark_unread'], value_width
        ),
        menu_format.format(
            'Toggle Star:', key_width, keys['star'], value_width
        ),
        menu_format.format(
            'Open in Browser:', key_width, keys['open_in_browser'], value_width
        ),
        menu_format.format(
            'Quit', key_width, keys['quit'], value_width
        ),
    ]

    return ''.join(menu)


if __name__ == '__main__':
    curses.wrapper(main)
