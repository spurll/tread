#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, dateutil, textwrap, sys
from shutil import get_terminal_size
from bs4 import BeautifulSoup
from dateutil.parser import parse


with open('config.yml') as f:
    config = yaml.load(f)


class Window:
    border_height = 1
    border_width = 2

    def __init__(
        self, screen,
        height=None, width=None, max_lines=None,
        row_offset=0, col_offset=0,
        border=True
    ):
        # Size information.
        self.full_height = height if height is not None else curses.LINES
        self.full_width = width if width is not None else curses.WIDTH
        self.max_lines = config.get('buffer_lines', 1000)   # This is a kludge.
        # TODO: We may need to figure out how to scroll the sidebar.

        # Position information.
        self.row_offset = row_offset
        self.col_offset = col_offset
        self.scroll_pos = 0

        # Curses setup.
        self.screen = screen
        self.window = curses.newwin(
            self.full_height, self.full_width, self.row_offset, self.col_offset
        )
        self.pad = curses.newpad(self.max_lines, self.width)

        # Border setup.
        if border:
            self.window.border()
            self.window.noutrefresh()
            curses.doupdate()

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

    def resize(self, height, width):
        # TODO
        pass


def main(screen):
    # Set up requests to fetch data with retries.
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=config.get('retries'))
    session.mount('http://', adapter)

    # Fetch all feed data.
    feeds = list(map(
        lambda url:
            parse_feed(session.get(url, timeout=config.get('timeout')).text),
        config['feeds']
    ))

    # Ensure config['keys'] exists and make all keys uppercase.
    config['keys'] = configure_keys(config.get('keys', dict()))

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Create screen objects.
    # TODO: Ensure screen is large enough to accommodate sidebar and content.
    sidebar = Window(screen, width=40, max_lines=200)
    content = Window(screen, width=curses.COLS - 40, col_offset=40)

    # Add title.
    title=config.get('title', 'TREAD')
    screen.addnstr(
        0, centre(title, sidebar.full_width), title, sidebar.full_width
    )

    # Turn off visible cursor.
    curses.curs_set(False)

    # Initial selections.
    selected_feed = 0
    selected_item = 0


    # TODO: Feed selection, item selection, etc. should probably be abstracted
    # into an object as well. These loops are really awkward, as is the line-
    # counting.


    while True:
        # Print sidebar.
        for i, feed in enumerate(feeds):
            sidebar.print(
                '{:{}}'.format(feed['title'], sidebar.width),
                row_offset=i,
                attr=curses.A_REVERSE if i == selected_feed else curses.A_BOLD
            )

            if i == selected_feed:
                current_feed = feed

        # Refresh sidebar.
        sidebar.refresh()

        # Print content.
        line = 0
        for i, item in enumerate(current_feed['items']):
            if line >= content.max_lines: break
            # TODO: This is a terrible kludge. At least warn or something.

            content.print(
                '{:{}}{:%Y-%m-%d %H:%M}'.format(
                    item['title'], content.width - 16, item['date']
                ),
                row_offset=line,
                attr=curses.A_REVERSE if i == selected_item else curses.A_BOLD
            )
            line += 1

            if i == selected_item:
                current_item = item
                line += 1

                # Parse the HTML content.
                parsed_string = parse_html(
                    item['content'], content.width,
                    config.get('browser', 'lynx')
                )

                # Print it to the screen.
                content.print(parsed_string, row_offset=line)

                line += parsed_string.count('\n') + 1

        # Undo scrolling if content isn't big enough to scroll.
        content.constrain_scroll(line)
        content.refresh()

        # Block, waiting for input.
        key = screen.getkey().upper()

        if key == config['keys']['next_item']:
            content.clear() # Should be more selective.
            selected_item = (selected_item + 1) % len(current_feed['items'])
        elif key == config['keys']['prev_item']:
            content.clear() # Should be more selective.
            selected_item = (selected_item - 1) % len(current_feed['items'])
        elif key == config['keys']['next_feed']:
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0
        elif key == config['keys']['prev_feed']:
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0
        elif key == config['keys']['scroll_down']:
            content.clear() # Should be more selective.
            content.scroll_down()
        elif key == config['keys']['scroll_up']:
            content.clear() # Should be more selective.
            content.scroll_up()
        elif key == config['keys']['open_in_browser']:
            open_in_browser(current_item['url'])
        elif key == config['keys']['mark_read']:
            pass
        elif key == config['keys']['mark_unread']:
            pass
        elif key == config['keys']['star']:
            pass
        elif key == config['keys']['quit']:
            break


    # Write a message function that pops up an overlay window to display a
    # message and pauses for anykey



    # Looks like some unicode characters aren't working:
    # http://xkcd.com/1647/



    # In the DB should store/use guids.
    # Should probably store all of the articles in the DB, and sync them with
    # feeds on launch and on demand.

    # Do something about resize!

    # Display keyboard shortcuts at the bottom of the sidebar.
    # Keys:
    #   h/l: prev/next feed
    #   j/k: next/prev item
    #   up/down: scroll display pad (sidebar should scroll automatically)
    #   r/u: mark as read/unread
    #   s: save/star/unsave/unstar
    #   o: open in browser



    # Warn that this will probably only work in lynx (or implement both...?)
    # Insert output from jp2a on its own lines before the image tag (leave it)
    # if it's a JPG:
    #   jp2a https://spurll.com/Gem.jpg --width=X
    # otherwise:
    #   convert http://imgs.xkcd.com/comics/gravitational_waves.png jpg:- | jp2a - --invert --width=X

    # Also include html2text as a parser


def parse_feed(xml):
    soup = BeautifulSoup(xml, 'html.parser')

    return {
        'title': soup.channel.title.string,
        'url': soup.channel.link.string,
        'description': soup.channel.description.string,
        'items': [
            {
                'title': item.title.string,
                'url': item.link.string,
                'date': parse(item.pubdate.string).astimezone(tz=None),
                'id': item.guid.string,
                'content':
                    (item.find('content:encoded') or item.description).string
            }
            for item in soup.find_all('item')
        ]
    }


def parse_html(content, width, browser):
    if browser in ['lynx']:
        command = ['lynx','-stdin','-dump','-width',str(width),'-image_links']
        encoding = 'iso-8859-1'
    elif browser == 'w3m':
        command = ['w3m', '-T', 'text/html', '-dump', '-cols', str(width)]
        encoding = 'utf-8'
    else:
        Exception('Unsuported browser: {}'.format(browser))

    output = subprocess.check_output(
        command,
        input=content.encode(encoding, 'xmlcharrefreplace'),
        stderr=subprocess.STDOUT
    )
    output = output.decode(encoding, 'xmlcharrefreplace')

    return output


def open_in_browser(url):
    if sys.platform.startswith('linux'):
        subprocess.Popen(['xdg-open', url])
    elif sys.platform.startswith('darwin'):
        subprocess.Popen(['open', url])


def centre(text, width):
    return (width - len(text)) // 2


def configure_keys(existing):
    default = {
        'next_item': 'J',
        'prev_item': 'K',
        'next_feed': 'L',
        'prev_feed': 'H',
        'scroll_down': 'KEY_DOWN',
        'scroll_up': 'KEY_UP',
        'open_in_browser': 'O',
        'mark_read': 'R',
        'mark_unread': 'U',
        'star': 'S',
        'quit': 'Q'
    }

    # Make uppercase.
    existing = {key: value.upper() for key, value in existing.items()}

    # Return default keys, overwriting with the keys that exist in config.
    return {**default, **existing}


if __name__ == '__main__':
    curses.wrapper(main)
