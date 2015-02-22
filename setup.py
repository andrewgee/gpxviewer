#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

setup(name="gpxviewer",
	version="0.5.1",
	author="Andrew Gee",
	author_email="andrew@andrewgee.org",
	maintainer="Andrew Gee",
	maintainer_email="andrew@andrewgee.org",
	description="GPS Trace Viewer and Analyser",
	long_description="GPX Viewer is a simple way to review those GPS traces you've made whilst on the move. Find out interesting stats and see a map overlay of the journey.",
	url="http://andrewgee.org/blog/gpxviewer",
	license="GNU General Public License (GPL)",
	platforms="linux",
	packages=["gpxviewer","gpxviewer.utils","gpxviewer.utils.iso8601","gpxviewer.utils.timezone","gpxviewer.pygtk_chart"],
	data_files=[
		('share/gpxviewer/ui/', ['ui/gpxviewer.ui','ui/gpxviewer.png','ui/gpxviewer.svg','gpxviewer/pygtk_chart/data/tango.color']),
		('share/pixmaps', ['ui/gpxviewer.svg']) 
	],
	scripts = ['bin/gpxviewer'],
      cmdclass = { "build" :  build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                 }
)
