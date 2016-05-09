import curses
from dateutil.parser import parse
from datetime import datetime
from bs4 import BeautifulSoup
from imgii import image_to_ascii
from sqlalchemy import Column, ForeignKey
from sqlalchemy import Integer, Unicode, UnicodeText, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Feed(Base):
    __tablename__ = 'feeds'

    id = Column(Integer, primary_key=True)
    url = Column(Unicode, index=True)
    name = Column(Unicode)
    main_url = Column(Unicode)
    description = Column(UnicodeText)
    last_refresh = Column(DateTime)

    items = relationship(
        'Item', order_by='desc(Item.date)', back_populates='feed'
    )

    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.main_url = ''
        self.description = ''
        self.last_refresh = None

    # Update object from web and write back to DB.
    def refresh(self, db_session, www_session, timeout, log):
        log('Refreshing {}...'.format(self.name))
        try:
            r = www_session.get(self.url, timeout=timeout)
        except:
            log('Unable to refresh: no response from {}.'.format(self.url))
            return

        if r.status_code != 200:
            log(
                'Unable to refresh: {} responded with {}.'.format(
                    self.url, r.status_code
                )
            )
            return

        xml = r.text
        soup = BeautifulSoup(xml, 'html.parser')

        # TODO: Add support for ATOM feeds as well.

        # Nope, just use the name from the config file.
        # self.name = soup.channel.name.string

        self.main_url = soup.channel.link.string
        self.description = soup.channel.description.string

        for item in soup.find_all('item'):
            guid = item.guid.string
            row = db_session.query(Item).filter(Item.feed_id == self.id) \
                .filter(Item.guid == guid).scalar()

            if row:
                # Update the item.
                row.title = item.title.string
                row.url = item.link.string
                row.date = parse(item.pubdate.string)
                row.content = (
                    item.find('content:encoded') or item.description
                ).string

            else:
                # Create the item.
                row = Item(
                    guid=guid,
                    title=item.title.string,
                    url=item.link.string,
                    date=parse(item.pubdate.string),
                    content=(
                        item.find('content:encoded') or item.description
                    ).string
                )
                self.items.append(row)

        # Feed has been refreshed.
        self.last_refresh = datetime.utcnow()

        # Write back to DB.
        db_session.add(self)
        db_session.commit()


class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    guid = Column(Unicode, index=True)
    title = Column(Unicode)
    url = Column(Unicode)
    date = Column(DateTime)
    content = Column(UnicodeText)
    read = Column(Boolean, default=False)
    starred = Column(Boolean, default=False)

    feed_id = Column(Integer, ForeignKey('feeds.id'))
    feed = relationship('Feed', back_populates='items')


class Window:
    border_height = 1
    border_width = 2

    def __init__(
        self, screen, height=None, width=None, row_offset=0, col_offset=0,
        max_lines=1000, border=True, title=''
    ):
        # Size information.
        self.full_height = height if height is not None else curses.LINES
        self.full_width = width if width is not None else curses.COLS
        self.max_lines = max_lines
        # TODO: We may need to figure out how to scroll the sidebar.

        # Position information.
        self.row_offset = row_offset
        self.col_offset = col_offset
        self.scroll_pos = 0
        self.next_row = 0

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

        # Border and title setup.
        self.border = border
        self.title = title

        # Refreshing border also refreshes the title.
        self.refresh_border()

    @property
    def height(self):
        return self.full_height - 2 * Window.border_height

    @property
    def width(self):
        return self.full_width - 2 * Window.border_width

    def write(
        self, string, row_offset=None, col_offset=0, attr=curses.A_NORMAL,
        autoscroll=False
    ):
        if row_offset is None:
            row_offset = self.next_row

        try:
            self.pad.addstr(row_offset, col_offset, string, attr)
        except curses.error:
            # Lazy way to prevent writing too many buffer lines. Ugh.
            self.max_lines += 10
            self.pad.resize(self.max_lines, self.width)
            self.pad.addstr(row_offset, col_offset, string, attr)

        self.next_row = row_offset + 1
        # TODO: Shouldn't be +1: should figure out if it's a multiline thing.

        if autoscroll:
            self.scroll(self.next_row - self.height)


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
        try:
            self.pad.refresh(
                self.scroll_pos, 0,
                Window.border_height + self.row_offset,
                Window.border_width + self.col_offset,
                Window.border_height + self.row_offset + self.height - 1,
                Window.border_width + self.col_offset + self.width - 1
            )
        except:
            # Curses is garbage.
            pass

    def refresh_border(self):
        if self.border:
            self.window.border()

        if self.title:
            self.window.addstr(0, self.centre(self.title), self.title)

        self.window.refresh()

    def centre(self, text):
        return (self.full_width - len(text)) // 2

    def resize(
        self, new_height, new_width, new_row_offset=None, new_col_offset=None
    ):
        self.full_height = new_height
        self.full_width = new_width

        if new_row_offset is not None:
            self.row_offset = new_row_offset

        if new_col_offset is not None:
            self.col_offset = new_col_offset

        # These should probably be resize (and move) calls, but that's
        # complicated and (apparently) not recommended.
        del self.window
        self.window = curses.newwin(
            self.full_height, self.full_width, self.row_offset, self.col_offset
        )

        del self.pad
        self.pad = curses.newpad(self.max_lines, self.width)

        self.refresh_border()
