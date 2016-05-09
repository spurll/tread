#!/usr/bin/env python3

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml, curses, textwrap, sys, os
from argparse import ArgumentParser
from functools import partial
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Window, Feed, Item


def console_main():
    parser = ArgumentParser(description='A simple terminal feed reader.')
    parser.add_argument(
        'config', nargs='?', help='Path to the configuration file to use. '
        'Defaults to ~/.tread.yml.', default='~/.tread.yml'
    )
    args = parser.parse_args()

    curses.wrapper(partial(main, config_file=os.path.expanduser(args.config)))


def main(screen, config_file):
    # Load configuration.
    with open(config_file) as f:
        config = yaml.load(f)

    # Ensure config['keys'] exists and make all keys uppercase.
    config['keys'] = configure_keys(config.get('keys', dict()))

    # Set up database and session.
    db_path = os.path.expanduser(config.get('database', '~/.tread.db'))
    db_uri = 'sqlite:///{}'.format(db_path)
    engine = create_engine(db_uri)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()

    # Set up requests to fetch data with retries.
    www_session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        max_retries=config.get('retries', 10)
    )
    www_session.mount('http://', adapter)

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Turn off visible cursor.
    curses.curs_set(False)

    # Create screen objects.
    content, sidebar, menu, messages = init_windows(screen, config)

    # Add key listing to menu.
    menu.write(menu_text(config['keys'], menu.width))
    menu.refresh()

    # Add loading message.
    def log(message):
        messages.write(
            '{:%Y-%m-%d %H:%M}: {}'.format(datetime.now(), message),
            autoscroll=True
        )
        messages.refresh()

    # TODO: Auto-expand option (off), otherwise hit SPACE to expand and display
    # stuff. (Only mark as read when expanded. If auto-expand is on, only mark
    # as read when CONFIGURABLE VALUE seconds has passed.)

    # TODO: Add ability to do 10j or 10<DOWN_ARROW>, like in vim. Clear it
    # whenever a non-numeric key is hit.

    # TODO: Add read/starred state to display

    # TODO: Add optional unread count.

    # Load feeds from the DB.
    feeds = []
    for feed in config['feeds']:
        row = db_session.query(Feed).filter(Feed.url == feed['url']).scalar()

        if row:
            row.name = feed.get('name', row.name)
        else:
            row = Feed(feed.get('name', feed['url']), feed['url'])
            db_session.add(row)
            db_session.commit()

        feeds.append(row)

    # Initial selections.
    if len(feeds) > 0:
        feeds[0].refresh(db_session, www_session, config.get('timeout'), log)

    selected_feed = 0
    selected_item = 0

    # TODO: Feed selection, item selection, etc. should probably be abstracted
    # into an object as well. These loops are really awkward, as is the line-
    # counting.

    while True:
        current_item = None

        # Print sidebar.
        for i, feed in enumerate(feeds):
            sidebar.write(
                '{:{}}'.format(feed.name, sidebar.width),
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
            content.write(
                '{:{}}{:%Y-%m-%d %H:%M}'.format(
                    item.title, content.width - 16, item.date
                ) if len(item.title) + 16 < content.width else '{:{}}'.format(
                    item.title, content.width
                ),
                row_offset=line,
                attr=curses.A_REVERSE if i == selected_item else curses.A_BOLD
            )
            line += 1

            if i == selected_item:
                current_item = item
                line += 1

                # Parse the HTML content.
                parsed_string = parse_content(
                    item.content, config.get('browser', 'lynx'), content.width
                )

                # Print it to the screen.
                content.write(parsed_string, row_offset=line)

                line += parsed_string.count('\n') + 1

        # Undo scrolling if content isn't big enough to scroll.
        content.constrain_scroll(line)
        content.refresh()

        # Block, waiting for input.
        try:
            key = screen.getkey().upper()
        except:
            # On resize, getkey screws up once (maybe more).
            pass

        if key == 'KEY_RESIZE':
            resize(content, sidebar, menu, messages)
            # TODO: Doesn't work anymore?
            menu.write(menu_text(config['keys'], menu.width))
            menu.refresh()

        elif key == config['keys']['next_item']:
            if len(current_feed.items) > 0:
                content.clear() # Should be more selective.
                selected_item = (selected_item + 1) % len(current_feed.items)

        elif key == config['keys']['prev_item']:
            if len(current_feed.items) > 0:
                content.clear() # Should be more selective.
                selected_item = (selected_item - 1) % len(current_feed.items)

        elif key == config['keys']['next_feed']:
            content.clear()
            sidebar.clear() # Should be more selective.

            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0

            if (feeds[selected_feed].last_refresh is None) or (
                datetime.utcnow() - feeds[selected_feed].last_refresh >
                    timedelta(minutes=config.get('refresh', 10))
            ):
                feeds[selected_feed].refresh(
                    db_session, www_session, config.get('timeout'), log
                )

        elif key == config['keys']['prev_feed']:
            content.clear()
            sidebar.clear() # Should be more selective.

            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0

            if (feeds[selected_feed].last_refresh is None) or (
                datetime.utcnow() - feeds[selected_feed].last_refresh >
                    timedelta(minutes=config.get('refresh', 10))
            ):
                feeds[selected_feed].refresh(
                    db_session, www_session, config.get('timeout'), log
                )

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

    # TODO: Looks like some unicode characters aren't working:
    # http://xkcd.com/1647/

    # TODO: Warn that this will probably only work in lynx (or implement both...?)
    # Insert output from image conversion on its own lines before the image tag
    # (leave it)
    # use image_to_ascii()

    # TODO: Also include html2text as a parser


def init_windows(screen, config):
    content = Window(
        screen, *content_dimensions(),
        max_lines=config.get('buffer_lines', 1000), title='TREAD'
    )

    sidebar = Window(
        screen, *sidebar_dimensions(), max_lines=100, title='FEEDS'
    )

    menu = Window(
        screen, *menu_dimensions(), max_lines=7 + 2 * Window.border_height,
        title='KEYS'
    )

    messages = Window(
        screen, *message_dimensions(), max_lines=10, title='MESSAGES'
    )

    return (content, sidebar, menu, messages)


def parse_content(content, browser, width):
    if browser == 'lynx':
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


def open_in_browser(url):
    if sys.platform.startswith('linux'):
        subprocess.Popen(['xdg-open', url])
    elif sys.platform.startswith('darwin'):
        subprocess.Popen(['open', url])


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
    value_width = max(0, width - key_width)
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


# This is awful.
def resize(content, sidebar, menu, messages):
    curses.update_lines_cols()  # Requires Python 3.5.
    sidebar.resize(*sidebar_dimensions())
    menu.resize(*menu_dimensions())
    content.resize(*content_dimensions())
    messages.resize(*message_dimensions())
    # TODO: Also re-clear the vertical space between sidebar and contents!


def sidebar_width():
    # Sidebar and menu width should half of screen up to a desired maximum.
    return min(40, curses.COLS // 2)


def menu_height():
    # Menu height should be a third of screen up to the number of menu items.
    return min(7 + 2 * Window.border_height, curses.LINES // 3)


def message_height():
    # Message height should be 50% of screen up to four lines of content.
    return min(4 + 2 * Window.border_height, curses.LINES // 3)


def sidebar_dimensions():
    return (
        curses.LINES - menu_height() - message_height(), sidebar_width(), 0, 0
    )


def menu_dimensions():
    return (
        menu_height(), sidebar_width(),
        curses.LINES - menu_height() - message_height(), 0
    )


def message_dimensions():
    return (message_height(), curses.COLS, curses.LINES - message_height(), 0)


def content_dimensions():
    return (
        curses.LINES - message_height(), curses.COLS - sidebar_width() - 1,
        0, sidebar_width() + 1
    )


if __name__ == '__main__':
    console_main()
