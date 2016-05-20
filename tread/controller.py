import os
import shutil
import subprocess
import requests
import yaml
import curses
import webbrowser
import re
import imgii
from datetime import datetime, timedelta, timezone
from html2text import HTML2Text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base, Window, Feed


LOGO = [
    r" _____                 _             ",
    r"|_   _|_ ___  __ _  __| |  by        ",
    r"  | | `_| _ \/ _` |/ _` |  Gem Newman",
    r"  | | ||  __/ (_| | (_| |            ",
    r"  |_|_| \___\\__'_|\__'_|  spurll.com"
]


def update_feeds(config_file):
    # Load configuration.
    with open(config_file) as f:
        config = yaml.load(f)

    # Set up database and requests sessions.
    db_session, www_session = configure_sessions(config)

    for feed in config.get('feeds', []):
        # Load feeds from the database.
        row = db_session.query(Feed).filter(Feed.url == feed['url']).scalar()

        if row:
            row.name = feed.get('name', row.name)
        else:
            row = Feed(feed.get('name', feed['url']), feed['url'])
            db_session.add(row)
            db_session.commit()

        # Update feed items.
        row.refresh(db_session, www_session, config.get('timeout'))


def main(screen, config_file):
    # Find configuration file.
    missing_config = not os.path.isfile(config_file)

    if missing_config:
        # Write default configuration to config file location.
        sample_config = os.path.realpath(
            os.path.join(os.path.dirname(__file__), 'default_config.yml')
        )
        missing_sample = not os.path.isfile(sample_config)

        if not missing_sample:
            shutil.copyfile(sample_config, config_file)

    # Load configuration.
    try:
        with open(config_file) as f:
            config = yaml.load(f)
    except:
        config = {'feeds': []}

    # Ensure config['keys'] exists and make all keys uppercase.
    config['keys'] = configure_keys(config.get('keys', dict()))

    # Set up database and requests sessions.
    db_session, www_session = configure_sessions(config)

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Turn off visible cursor.
    curses.curs_set(False)

    # Create screen objects.
    content, logo, sidebar, menu, messages = init_windows(screen, config)

    # Write logo to screen.
    draw_logo(logo)

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

    if missing_config and missing_sample:
        log(
            'No configuration file found at {}. Please consult the readme '
            'document.'.format(config_file)
        )
    elif missing_config:
        log(
            'No configuration file found at {}. A default configuration file '
            'has been provided.'.format(config_file)
        )

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
    if (len(feeds) > 0) and (
        (feeds[0].last_refresh is None) or (
            datetime.utcnow() - feeds[0].last_refresh >
            timedelta(minutes=config.get('refresh', 10))
        )
    ):
        feeds[0].refresh(db_session, www_session, config.get('timeout'), log)

    item_open = False
    autoscroll_to_item = False
    redraw_sidebar = True
    redraw_content = True
    selected_feed = 0
    selected_item = 0

    # TODO: Add ability to do 10j or 10<DOWN_ARROW>, like in vim. Clear it
    # whenever a non-numeric key is hit.

    # TODO: Add g/gg (or something) for top/bottom of feed items

    # TODO: Feed selection, item selection, etc. should probably be abstracted
    # into an object as well. These loops are really awkward.

    while True:
        current_feed = feeds[selected_feed] if feeds else None
        current_item = (
            current_feed.items[selected_item] if current_feed else None
        )

        if redraw_sidebar:
            redraw_sidebar = False
            for i, feed in enumerate(feeds):
                # Add optional unread count to feed name display.
                display_name = feed.name
                if config.get('unread_count'):
                    display_name += ' ({}{})'.format(
                        feed.unread,
                        ', *{}'.format(feed.starred) if feed.starred else ''
                    )

                sidebar.write(
                    '{:{}}'.format(display_name, sidebar.width), row_offset=i,
                    attr=curses.A_BOLD | curses.A_REVERSE * (i==selected_feed)
                )

            # Refresh sidebar.
            sidebar.refresh()

        if redraw_content:
            redraw_content = False
            if current_feed:
                for i, item in enumerate(current_feed.items):
                    attributes = (
                        curses.A_REVERSE * (i == selected_item) |
                        curses.A_BOLD * (not item.read)
                    )

                    if len(item.title) + 16 < content.width:
                        # There is space for a date.
                        content.write(
                            '{:{}}{:%Y-%m-%d %H:%M}'.format(
                                ('*' if item.starred else '') + item.title,
                                content.width - 16, to_local(item.date)
                            ),
                            row_offset=0 if i == 0 else None, attr=attributes
                        )
                    else:
                        # No space to include the date.
                        content.write(
                            '{:{}}'.format(
                                ('*' if item.starred else '') + item.title,
                                content.width
                            ),
                            row_offset=0 if i == 0 else None, attr=attributes
                        )

                    if i == selected_item:
                        # Autoscroll if newly-selected content is offscreen.
                        if autoscroll_to_item:
                            content.constrain_scroll(
                                first_line=max(
                                    content.next_row - content.height, 0
                                ),
                                last_line=content.height + content.next_row - 1
                            )
                            # Not perfect, because sometimes when items are
                            # open only the title will be visible. Oh well.
                            autoscroll_to_item = False

                        if item_open:
                            # Parse the HTML content.
                            parsed_string = parse_content(
                                item.content, config, content.width, log
                            )

                            # Print it to the screen.
                            content.write('\n{}'.format(parsed_string))

            else:
                log(
                    'No feeds to display. Instructions for adding feeds are '
                    'available in the readme document.'
                )

            content.refresh()

        # Block, waiting for input.
        try:
            key = screen.getkey().upper()
        except:
            # On resize, getkey screws up once (maybe more).
            pass

        if key == 'KEY_RESIZE':
            resize(content, logo, sidebar, menu, messages)
            draw_logo(logo)
            menu.write(menu_text(config['keys'], menu.width), row_offset=0)
            menu.refresh()
            redraw_content = True
            redraw_sidebar = True

        elif key == config['keys']['open'] and current_item:
            content.clear()     # Should be more selective.
            redraw_content = True
            item_open = not item_open

            if item_open:
                current_item.read = True
                db_session.commit()
            else:
                # When closed, title might be off the screen now.
                autoscroll_to_item = True

        elif key == config['keys']['next_item'] and current_feed:
            if len(current_feed.items) > 0:
                content.clear()     # Should be more selective.
                redraw_content = True
                selected_item = (selected_item + 1) % len(current_feed.items)
                autoscroll_to_item = True

                if item_open:
                    current_feed.items[selected_item].read = True
                    db_session.commit()

        elif key == config['keys']['prev_item'] and current_feed:
            if len(current_feed.items) > 0:
                content.clear()     # Should be more selective.
                redraw_content = True
                selected_item = (selected_item - 1) % len(current_feed.items)
                autoscroll_to_item = True

                if item_open:
                    current_feed.items[selected_item].read = True
                    db_session.commit()

        elif key == config['keys']['next_feed'] and current_feed:
            content.clear()     # Should be more selective.
            sidebar.clear()     # Should be more selective.
            redraw_content = True
            redraw_sidebar = True

            selected_feed = (selected_feed + 1) % len(feeds)
            selected_item = 0
            item_open = False
            autoscroll_to_item = True

            if (feeds[selected_feed].last_refresh is None) or (
                datetime.utcnow() - feeds[selected_feed].last_refresh >
                    timedelta(minutes=config.get('refresh', 10))
            ):
                feeds[selected_feed].refresh(
                    db_session, www_session, config.get('timeout'), log
                )

        elif key == config['keys']['prev_feed'] and current_feed:
            content.clear()     # Should be more selective.
            sidebar.clear()     # Should be more selective.
            redraw_content = True
            redraw_sidebar = True

            selected_feed = (selected_feed - 1) % len(feeds)
            selected_item = 0
            item_open = False
            autoscroll_to_item = True

            if (feeds[selected_feed].last_refresh is None) or (
                datetime.utcnow() - feeds[selected_feed].last_refresh >
                    timedelta(minutes=config.get('refresh', 10))
            ):
                feeds[selected_feed].refresh(
                    db_session, www_session, config.get('timeout'), log
                )

        elif key == config['keys']['scroll_down']:
            content.scroll_down(config.get('scroll_lines', 5))

        elif key == config['keys']['scroll_up']:
            content.scroll_up(config.get('scroll_lines', 5))

        elif key == config['keys']['open_in_browser'] and current_item:
            webbrowser.open(current_item.url)

        elif key == config['keys']['toggle_read'] and current_item:
            # Should be more selective.
            redraw_content = True
            redraw_sidebar = True
            current_item.read = not current_item.read
            db_session.commit()

        elif key == config['keys']['toggle_star'] and current_item:
            # Should be more selective.
            redraw_content = True
            redraw_sidebar = True
            current_item.starred = not current_item.starred
            db_session.commit()

        elif key == config['keys']['quit']:
            break


def configure_sessions(config):
    # Set up database session.
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

    return (db_session, www_session)


def init_windows(screen, config):
    content = Window(
        screen, *content_dimensions(),
        max_lines=config.get('buffer_lines', 1000)
    )

    logo = Window(
        screen, *logo_dimensions(), max_lines=len(LOGO), border=False
    )

    sidebar = Window(
        screen, *sidebar_dimensions(), max_lines=100, title='FEEDS'
    )

    menu = Window(screen, *menu_dimensions(), max_lines=8, title='KEYS')

    messages = Window(
        screen, *message_dimensions(), max_lines=10, title='MESSAGES'
    )

    return (content, logo, sidebar, menu, messages)


def parse_content(content, config, width, log):
    browser = config.get('parser', 'html2text')
    images = config.get('ascii_images')
    chars = imgii.BLOCKS if config.get('image_blocks') else imgii.CHARS

    if images:
        # Replace images with placeholder text, because (especially if using
        # block characters) the images don't always survive parsing.
        content = re.sub(
            r'(<img\s.*?src="(https?://.+?)"[^>]*?>)',
            r'<br/>TREAD_PLACEHOLDER \2 END_PLACEHOLDER<br/>\1',
            content
        )

    if browser == 'lynx':
        output = subprocess.check_output(
            [
                'lynx',
                '-stdin', '-dump', '-width', str(width + 2), '-image_links'
            ],
            input=content.encode('iso-8859-1', 'xmlcharrefreplace'),
            stderr=subprocess.STDOUT
        )
        output = output.decode('iso-8859-1', 'xmlcharrefreplace')
        output += '\n'

    elif browser == 'w3m':
        output = subprocess.check_output(
            ['w3m', '-T', 'text/html', '-dump', '-cols', str(width)],
            input=content.encode('utf-8', 'xmlcharrefreplace'),
            stderr=subprocess.STDOUT
        )
        output = output.decode('utf-8', 'xmlcharrefreplace')

    elif browser == 'html2text':
        handler = HTML2Text()
        handler.body_width = width - 1
        output = handler.handle(content)

    else:
        log('Unsuported browser: {}'.format(browser))
        return content

    if images:
        output = re.sub(
            r'\n? *TREAD_PLACEHOLDER[\s\n]+?(.+?)[\s\n]+?END_PLACEHOLDER',
            lambda m: '\n   ' + imgii.image_to_ascii(
                re.sub(r'[\s\n]', '', m.group(1)),
                url=True, console_width=width - 7, chars=chars
            ).replace('\n', '\n   '),
            output,
            flags=re.DOTALL
        )

    return output


def configure_keys(existing):
    default = {
        'open': ' ',
        'prev_item': 'K',
        'next_item': 'J',
        'prev_feed': 'H',
        'next_feed': 'L',
        'scroll_up': 'KEY_UP',
        'scroll_down': 'KEY_DOWN',
        'toggle_read': 'R',
        'toggle_star': 'S',
        'open_in_browser': 'O',
        'quit': 'Q'
    }

    # Make uppercase.
    existing = {key: value.upper() for key, value in existing.items()}

    # Return default keys, overwriting with the keys that exist in config.
    return {**default, **existing}


def menu_text(keys, width):
    key_width = 16
    value_width = max(0, width - key_width)
    menu_format = '{:<{}}{:>{}}'

    # Make the display names a little nicer.
    disp = {
        k: v.replace('KEY_', '') if v != ' ' else 'SPACE'
        for k, v in keys.items()
    }

    menu = [
        menu_format.format(
            'Open/Close Item:', key_width, disp['open'], value_width
        ),
        menu_format.format(
            'Prev/Next Item:', key_width,
            disp['prev_item'] + '/' + disp['next_item'], value_width
        ),
        menu_format.format(
            'Prev/Next Feed:', key_width,
            disp['prev_feed'] + '/' + disp['next_feed'], value_width
        ),
        menu_format.format(
            'Scroll Up/Down:', key_width,
            disp['scroll_up'] + '/' + disp['scroll_down'], value_width
        ),
        menu_format.format(
            'Toggle Read:', key_width, disp['toggle_read'], value_width
        ),
        menu_format.format(
            'Toggle Star:', key_width, disp['toggle_star'], value_width
        ),
        menu_format.format(
            'Open in Browser:', key_width, disp['open_in_browser'], value_width
        ),
        menu_format.format('Quit', key_width, disp['quit'], value_width),
    ]

    return ''.join(menu)


# This is awful.
def resize(content, logo, sidebar, menu, messages):
    curses.update_lines_cols()  # Requires Python 3.5.

    logo.resize(*logo_dimensions())
    sidebar.resize(*sidebar_dimensions())
    menu.resize(*menu_dimensions())
    content.resize(*content_dimensions())
    messages.resize(*message_dimensions())


def sidebar_width():
    # Sidebar and menu width should half of screen up to a desired maximum.
    return min(45, curses.COLS // 2)


def logo_height():
    # Logo height should be a quarter of screen up to the number of lines.
    return min(len(LOGO) + 1, curses.LINES // 4)


def menu_height():
    # Menu height should be a quarter of screen up to the number of menu items.
    return min(8 + 2 * Window.border_height, curses.LINES // 4)


def message_height():
    # Message height should be a quarter of screen up to four lines of content.
    return min(4 + 2 * Window.border_height, curses.LINES // 4)


def logo_dimensions():
    return (logo_height(), sidebar_width(), 0, 0)


def sidebar_dimensions():
    return (
        curses.LINES - logo_height() - menu_height() - message_height(),
        sidebar_width(), logo_height(), 0
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


def draw_logo(window):
    for i, line in enumerate(LOGO):
        window.write(
            line, row_offset=i, col_offset=window.centre(line),
            attr=curses.A_BOLD
        )

    window.refresh()


def to_local(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
