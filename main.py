#!/usr/bin/env python
#
#  main.py - Launcher for GPX Viewer
#
#  Copyright (C) 2009 Andrew Gee
#
#  GPX Viewer is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#  
#  GPX Viewer is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License along
#  with this program.  If not, see <http://www.gnu.org/licenses/>.

#
#  If you're having any problems, don't hesitate to contact: andrew@andrewgee.org
#
import sys, os.path

parent_dir = os.path.dirname(os.path.abspath(__file__))
source_dir = os.path.join(parent_dir, "gpxviewer")
sys.path.append(source_dir)

from gi.repository import Gdk
from gpxviewer.ui import MainWindow
 
Gdk.threads_init()

if len(sys.argv) > 2:
	files = sys.argv[1:]
elif len(sys.argv) > 1:
	files = [sys.argv[1]]
else:
	files = []

ui_dir = os.path.join(parent_dir, "ui/")

gui = MainWindow(
		ui_dir=ui_dir,
		files=files
).main()

