#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, dateutil, textwrap
from shutil import get_terminal_size
from bs4 import BeautifulSoup
from dateutil.parser import parse


def main(screen):
    with open('config.yml') as f:
        config = yaml.load(f)

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
                line += 1

                parsed_string = parse_html(
                    item['content'], content_width,
                    config.get('browser', 'lynx')
                )

                try:
                    content.addstr(line, 0, parsed_string)
                except curses.error:
                    pass    # Lazy way to prevent writing too many buffer lines

                line += parsed_string.count('\n') + 1

        # Undo scrolling if content isn't big enough to scroll.
        scroll_position = max(scroll_position, 0)
        scroll_position = min(scroll_position, line - height)

        content.noutrefresh(0 + scroll_position, 0, *content_pos)
        curses.doupdate()

        # Block, waiting for input.
        key = screen.getkey().upper()

        if key == 'Q':
            break
        elif key == 'H':
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0
        elif key == 'L':
            content.clear() # Should be more selective.
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0
        elif key == 'J':
            content.clear() # Should be more selective.
            selected_item = (selected_item + 1) % len(current_feed['items'])
        elif key == 'K':
            content.clear() # Should be more selective.
            selected_item = (selected_item - 1) % len(current_feed['items'])
        elif key == 'KEY_DOWN':
            content.clear() # Should be more selective.
            scroll_position += 1
        elif key == 'KEY_UP':
            content.clear() # Should be more selective.
            scroll_position -= 1




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

    # open in browser will depend on OS:
    # xdg-open in ubuntu
    # open in osx



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
        command = [
            'lynx', '-stdin', '-dump', '-width', str(width), '-image_links'
        ]
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


if __name__ == '__main__':
    curses.wrapper(main)
