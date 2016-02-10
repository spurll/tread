#!/usr/bin/env python

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    


import subprocess, requests, yaml
from shutil import get_terminal_size
from bs4 import BeautifulSoup


def main():
    with open('config.yml') as f:
        config = yaml.load(f)

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=config.get('retries'))
    session.mount('http://', adapter)

    feeds = map(
        lambda url:
            parse_feed(session.get(url, timeout=config.get('timeout')).text),
        config['feeds']
    )




    full_width = get_terminal_size().columns
    sidebar_width = 40
    content_width = full_width - sidebar_width


    for feed in feeds:
        print(parse_html(feed['items'][-1]['content'], content_width, config.get('browser', 'lynx')))








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
                'date': item.pubdate.string,
                'content':
                    (item.find('content:encoded') or item.description).string
            }
            for item in soup.find_all('item')
        ]
    }


def parse_html(content, width, browser):
    if browser in ['lynx']:
        command = ['lynx', '-stdin', '-dump', '-width', str(width), '-image_links']
    elif browser == 'w3m':
        command = ['w3m', '-T', 'text/html', '-dump', '-width', str(width)]
    else:
        Exception('Unsuported browser: {}'.format(browser))

    return subprocess.check_output(
        command, input=content, universal_newlines=True
    )


if __name__ == '__main__':
    main()
