#!/usr/bin/env python3

from setuptools import setup

setup(
    name='tread',
    packages=['tread'],
    scripts=['main.py'],
    include_package_data=True,
    version='0.9.6',
    description='A terminal feed reader.',
    url='https://github.com/spurll/tread',
    download_url='https://github.com/spurll/tread/tarball/0.9.5',
    author='Gem Newman',
    author_email='spurll@gmail.com',
    license='CC BY-SA 4.0',
    install_requires=[
        'requests >= 2.25',
        'beautifulsoup4 >= 4.11',
        'pyyaml >= 6',
        'imgii >= 0.3.1',
        'python-dateutil >= 2.8',
        'sqlalchemy >= 1.4',
        'html2text >= 2020',
        'wcwidth >= 0.2.5'
    ],
    entry_points={'console_scripts': ('tread = main:console_main')},
    keywords=['rss', 'feed', 'reader'],
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Environment :: Console :: Curses',
        'Development Status :: 4 - Beta',
        'Topic :: Internet',
        'Programming Language :: Python :: 3.9'
    ],
    zip_safe=False,
)
