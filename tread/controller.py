import subprocess, requests, yaml, curses, textwrap, sys

from tread.models import Window, Feed, Item


def main(screen, config_file):
    with open(config_file) as f:
        config = yaml.load(f)

    # Ensure config['keys'] exists and make all keys uppercase.
    config['keys'] = configure_keys(config.get('keys', dict()))

    # Set up requests to fetch data with retries.
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        max_retries=config.get('retries', 10)
    )
    session.mount('http://', adapter)

    # This is the only time the whole screen is ever refreshed. But if you
    # don't refresh it, screen.getkey will clear it, because curses is awful.
    screen.refresh()

    # Turn off visible cursor.
    curses.curs_set(False)

    # Create screen objects.
    # TODO: Ensure screen is large enough to accommodate sidebar and content.
    content, sidebar, menu = init_windows(
        screen, config.get('buffer_lines', 1000)
    )

    # Add key listing to menu.
    menu.write(menu_text(config['keys'], menu.width))
    menu.refresh()

    # TODO
    # For each feed in config, load contents from the DB.
    # Mark all as "needs refresh".
    # Since the top one is selected, refresh it.
    # Proceed to display.


    # Fetch all feed data.
    feeds = [
        Feed(
            url, session, config.get('refresh_rate', 10),
            config.get('timeout'), config.get('browser', 'lynx')
        )
        for url in config['feeds']
    ]

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
            sidebar.write(
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

            content.write(
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
                content.write(parsed_string, row_offset=line)

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



def init_windows(screen, buffer_lines):
    menu_items = 7
    menu_height = menu_items + 2 * Window.border_height

    content = Window(
        screen, width=-41, max_lines=buffer_lines, col_offset=41, title='TREAD'
    )

    sidebar = Window(
        screen, width=40, height=-menu_height, max_lines=200, title='FEEDS'
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
