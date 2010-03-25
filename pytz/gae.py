"""
    A pytz version that runs smoothly on Google App Engine.

    Based on http://appengine-cookbook.appspot.com/recipe/caching-pytz-helper/

    To use, add pytz to your path normally, but import it from the gae module:

        from pytz.gae import pytz

    Applied patches:

      - The zoneinfo dir is removed from pytz, as this module includes a ziped
        version of it.

      - pytz is monkey patched to load zoneinfos from a zipfile.

      - pytz is patched to not check all zoneinfo files when loaded. This is
        sad, I wish that was lazy, so it could be monkey patched. As it is,
        the zipfile patch doesn't work and it'll spend resources checking
        hundreds of files that we know aren't there.

    pytz caches loaded zoneinfos, and this module will additionally cache them
    in memcache to avoid unzipping constantly. The cache key includes the
    OLSON_VERSION so it is invalidated when pytz is updated.
"""
import os
import logging
import pytz
import zipfile
from cStringIO import StringIO

from google.appengine.api import memcache

zoneinfo = None
zoneinfo_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
    'zoneinfo.zip'))


def get_zoneinfo():
    """Cache the opened zipfile in the module."""
    global zoneinfo
    if zoneinfo is None:
        zoneinfo = zipfile.ZipFile(zoneinfo_path)

    return zoneinfo


class TimezoneLoader(object):
    """A loader that that reads timezones using ZipFile."""
    def __init__(self):
        self.available = {}

    def open_resource(self, name):
        """Opens a resource from the zoneinfo subdir for reading."""
        name_parts = name.lstrip('/').split('/')
        for part in name_parts:
            if part == os.path.pardir or os.path.sep in part:
                raise ValueError('Bad path segment: %r' % part)

        cache_key = 'pytz.zoneinfo.%s.%s' % (pytz.OLSON_VERSION, name)
        zonedata = memcache.get(cache_key)
        if zonedata is None:
            zonedata = get_zoneinfo().read('/'.join('zoneinfo', *name_parts))
            memcache.add(cache_key, zonedata)
            logging.info('Added timezone to memcache: %s' % cache_key)
        else:
            logging.info('Loaded timezone from memcache: %s' % cache_key)

        return StringIO(zonedata)

    def resource_exists(self, name):
        """Return true if the given resource exists"""
        if name not in self.available:
            try:
                get_zoneinfo().getinfo(os.path.join('zoneinfo',
                    *name.lstrip('/').split('/')))
                self.available[name] = True
            except KeyError:
                self.available[name] = False

        return self.available[name]


pytz.loader = TimezoneLoader()
