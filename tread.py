#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, dateutil
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

    # Initialize screen and windows.
    sidebar_window = curses.newwin(full_height, full_sidebar_width, 0, 0)
    content_window = curses.newwin(
        full_height, full_content_width, 0, full_sidebar_width
    )
    sidebar = curses.newpad(height, sidebar_width)
    sidebar_pos = (1, 2, 1 + height, 2 + sidebar_width)
    content = curses.newpad(height, content_width)
    content_pos = (
        1, 2 + full_sidebar_width,
        1 + height, 2 + full_sidebar_width + content_width
    )

    # Turn off visible cursor.
    curses.curs_set(0)

    # Set window borders.
    sidebar_window.border()
    content_window.border()
    sidebar_window.noutrefresh()
    content_window.noutrefresh()
    curses.doupdate()

    # Initial selections.
    selected_feed = 0
    selected_item = 0

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

                content.addstr(line, 0, parsed_string)
                line += parsed_string.count('\n') + 1

        content.noutrefresh(0, 0, *content_pos)
        curses.doupdate()

        # Block, waiting for input.
        key = content.getch()

        if key == ord('h'):
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0
        if key == ord('l'):
            sidebar.clear() # Should be more selective.
            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0
        elif key == ord('j'):
            content.clear() # Should be more selective.
            selected_item = (selected_item + 1) % len(current_feed['items'])
        elif key == ord('k'):
            content.clear() # Should be more selective.
            selected_item = (selected_item - 1) % len(current_feed['items'])




"""
When parsing the Ph entry: "He did it again"

Traceback (most recent call last):
  File "/usr/local/Cellar/python3/3.4.3/Frameworks/Python.framework/Versions/3.4/lib/python3.4/subprocess.py", line 609, in check_output
    output, unused_err = process.communicate(inputdata, timeout=timeout)
  File "/usr/local/Cellar/python3/3.4.3/Frameworks/Python.framework/Versions/3.4/lib/python3.4/subprocess.py", line 960, in communicate
    stdout, stderr = self._communicate(input, endtime, timeout)
  File "/usr/local/Cellar/python3/3.4.3/Frameworks/Python.framework/Versions/3.4/lib/python3.4/subprocess.py", line 1659, in _communicate
    self.stdout.encoding)
  File "/usr/local/Cellar/python3/3.4.3/Frameworks/Python.framework/Versions/3.4/lib/python3.4/subprocess.py", line 888, in _translate_newlines
    data = data.decode(encoding)
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe2 in position 578: invalid continuation byte
"""


    # There are unicode problems.



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




    # If you want to use Unicode...
    # import locale
    # locale.setlocale(locale.LC_ALL, '')
    # code = locale.getpreferredencoding()
    # Then use code as the encoding for str.encode() calls.
    # window.encoding might also be useful.



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
    elif browser == 'w3m':
        command = ['w3m', '-T', 'text/html', '-dump', '-cols', str(width)]
    else:
        Exception('Unsuported browser: {}'.format(browser))

    try:
        output = subprocess.check_output(
            command, input=content,
            universal_newlines=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        output = 'Unable to parse HTML with {}:\n{}'.format(browser, e.output)

    return output


if __name__ == '__main__':
    curses.wrapper(main)
