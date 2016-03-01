#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, dateutil, textwrap, sys
from shutil import get_terminal_size
from bs4 import BeautifulSoup
from dateutil.parser import parse


def main(screen):
    with open('config.yml') as f:
        config = yaml.load(f)
        # Ensure config['keys'] exists and make all keys uppercase.
        config['keys'] = configure_keys(config.get('keys', dict()))

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=config.get('retries'))
    session.mount('http://', adapter)

    feeds = list(map(
        lambda url:
            parse_feed(session.get(url, timeout=config.get('timeout')).text),
        config['feeds']
    ))



    # USE OBJECT ORIENTATION
    # make your own window objects with refresh methods
    #   each have pads in them
    # content and sidebar both inherit these
    # navigating or changing content triggers refresh



    # Define screen size.
    full_width, full_height = curses.COLS, curses.LINES
    full_sidebar_width = 40
    full_content_width = full_width - full_sidebar_width
    sidebar_width = full_sidebar_width - 4
    content_width = full_content_width - 4
    height = full_height - 2
    max_lines = config.get('buffer_lines', 1000)

    # Initialize screen and windows.
    sidebar_window = curses.newwin(full_height, full_sidebar_width, 0, 0)
    content_window = curses.newwin(
        full_height, full_content_width, 0, full_sidebar_width
    )
    sidebar = curses.newpad(max_lines, sidebar_width)
    sidebar_pos = (1, 2, height, 2 + sidebar_width)
    content = curses.newpad(max_lines, content_width)
    content_pos = (
        1, 2 + full_sidebar_width,
        height, 2 + full_sidebar_width + content_width
    )

    # Turn off visible cursor.
    curses.curs_set(False)

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Set window borders.
    sidebar_window.border()
    content_window.border()
    sidebar_window.noutrefresh()
    content_window.noutrefresh()
    title = config.get('title', 'TREAD')
    screen.addnstr(
        0, centre(title, full_sidebar_width - 2), title, full_sidebar_width - 2
    )
    curses.doupdate()

    # Initial selections.
    selected_feed = 0
    selected_item = 0
    scroll_position = 0

    while True:
        # Print sidebar.
        for i, feed in enumerate(feeds):
            sidebar.addnstr(
                i, 0, '{:{}}'.format(feed['title'], sidebar_width),
                sidebar_width,
                curses.A_REVERSE if i == selected_feed else curses.A_BOLD
            )

            if i == selected_feed:
                current_feed = feed

        # Refresh sidebar.
        sidebar.noutrefresh(0, 0, *sidebar_pos)
        curses.doupdate()

        # Print content.
        line = 0
        for i, item in enumerate(current_feed['items']):
            if line >= max_lines: break

            content.addnstr(
                    line, 0, '{:{}}{:%Y-%m-%d %H:%M}'.format(
                    item['title'], content_width - 16, item['date']
                ), content_width,
                curses.A_REVERSE if i == selected_item else curses.A_BOLD
            )
            line += 1

            if i == selected_item:
                current_item = item
                line += 1

                parsed_string = parse_html(
                    item['content'], content_width,
                    config.get('browser', 'lynx')
                )

                try:
                    content.addstr(line, 0, parsed_string)
                except curses.error:
                    # Lazy way to prevent writing too many buffer lines. Ugh.
                    pass

                line += parsed_string.count('\n') + 1

        # Undo scrolling if content isn't big enough to scroll.
        scroll_position = max(scroll_position, 0)
        scroll_position = min(scroll_position, line - height)

        content.noutrefresh(0 + scroll_position, 0, *content_pos)
        curses.doupdate()

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
            scroll_position += 1
        elif key == config['keys']['scroll_up']:
            content.clear() # Should be more selective.
            scroll_position -= 1
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
