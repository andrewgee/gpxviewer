#
#  ui.py - GUI for GPX Viewer
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
import sys,os
from datetime import *
try: 
   import pygtk 
   pygtk.require("2.16") 
except: 
   pass 
try: 
   import gtk 
except: 
   print "GTK is not installed" 
   sys.exit(1) 

import osmgpsmap
assert osmgpsmap.__version__ >= "0.7.1"

from gpx import GPXTrace, check_file

try:
	import gnome
	def show_url(url): gnome.url_show(url)
except:
	import os
	def show_url(url): os.system("xdg-open %s" % url)

from utils.timezone import LocalTimezone

import locale
import gettext
locale.setlocale(locale.LC_ALL, '')
# see http://bugzilla.gnome.org/show_bug.cgi?id=344926 for why the
# next two commands look repeated.
#gtk.glade.bindtextdomain('gpxviewer')
#gtk.glade.textdomain('gpxviewer')
gettext.bindtextdomain('gpxviewer')
gettext.textdomain('gpxviewer')
_ = gettext.lgettext

class MainWindow:
	def __init__(self,ui_dir="ui/",filename=None):
		self.localtz = LocalTimezone()
		
		self.wTree = gtk.Builder()
		self.wTree.set_translation_domain('gpxviewer')
		self.wTree.add_from_file("%sgpxviewer.ui" % ui_dir)
		
		signals = {
			"on_windowMain_destroy": self.quit,
			"on_menuitemQuit_activate": self.quit,
			"on_menuitemOpen_activate": self.opengpx,
			"on_buttonZoomIn_clicked": self.zoomMapIn,
			"on_buttonZoomOut_clicked": self.zoomMapOut,
			"on_menuitemAbout_activate": self.openAboutDialog,
		}
		
		self.wTree.get_object("windowMain").set_icon_from_file("%sgpxviewer.svg" % ui_dir)
		
		self.ui_dir = ui_dir
		
		home_dir = os.getenv('HOME','/var/tmp')
		cache_dir= home_dir + '/.cache/gpxviewer/tiles/'

		self.map = osmgpsmap.GpsMap(tile_cache=cache_dir)
		self.map.layer_add(
					osmgpsmap.GpsMapOsd(
						show_dpad=False,
						show_zoom=False,
						show_scale=True,
						show_coordinates=False))

		self.wTree.get_object("vbox3").add(self.map)
		self.wTree.get_object("vbox3").reorder_child(self.map, 0)
		
		self.wTree.connect_signals(signals)
		
		self.wTree.get_object("windowMain").show_all()
		self.wTree.get_object("windowMain").set_title(_("GPX Viewer"))

		if filename != None:
			self.trace = self.loadGPX(filename)
			if self.trace != False:
				self.updateForNewFile()
		
		self.wTree.get_object("menuitemHelp").connect("activate", lambda *a: show_url("https://answers.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemTranslate").connect("activate", lambda *a: show_url("https://translations.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemReportProblem").connect("activate", lambda *a: show_url("https://bugs.launchpad.net/gpxviewer/+filebug"))
	
	def openAboutDialog(self,w):
		dialog = self.wTree.get_object("dialogAbout")
		self.wTree.get_object("dialogAbout").set_icon_from_file("%sgpxviewer.svg" % self.ui_dir)
		dialog.connect("response", lambda *a: dialog.hide())
		dialog.show_all()
		
	def updateForNewFile(self):
		self.zoom = 12
		
		distance = self.trace.get_distance()
		maximum_speed = self.trace.get_maximum_speed()
		average_speed = self.trace.get_average_speed()
		duration = self.trace.get_duration()
		tracks = self.trace.get_points()
		clat, clon = self.trace.get_centre()
		gpxfrom = self.trace.get_gpxfrom().astimezone(self.localtz)
		gpxto = self.trace.get_gpxto().astimezone(self.localtz)
		
		self.setDistanceLabel(round(distance/1000,2))
		self.setMaximumSpeedLabel(maximum_speed)
		self.setAverageSpeedLabel(average_speed)
		self.setDurationLabel(int(duration/60),duration-(int(duration/60)*60))
		self.setLoggingDateLabel(gpxfrom.strftime("%x"))
		self.setLoggingTimeLabel(gpxfrom.strftime("%X"),gpxto.strftime("%X"))
		self.setCentre(clat,clon)
		
		self.clearTrack()
		for track in tracks:
		  for segment in track:
			  self.addTrack(segment)
		
		self.wTree.get_object("windowMain").set_title(_("GPX Viewer - %s") % self.trace.get_filename())
			
	def loadGPX(self, filename=None):
		result = None
		if filename == None:
			while result == None:
				result = self.chooseGPX()
			if result == False:
				return False
		else:
			if check_file(filename) != True:
				self.showGPXError(None)
				return False
			else:
				result = GPXTrace(filename)

		return result
		
	def chooseGPX(self):
		filechooser = gtk.FileChooserDialog(title=_("Choose a GPX file to Load"),action=gtk.FILE_CHOOSER_ACTION_OPEN,parent=self.wTree.get_object("windowMain"))
		filechooser.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_DELETE_EVENT)
		filechooser.add_button(gtk.STOCK_OPEN, gtk.RESPONSE_OK)
		filechooser.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		response = filechooser.run()
		filename = filechooser.get_filename()
		
		if response == gtk.RESPONSE_DELETE_EVENT:
			filechooser.destroy()
			return False
		
		if check_file(filename) != True:
			self.showGPXError(filechooser)
			filechooser.destroy()		
			return None
		
		filechooser.destroy()
		
		trace = GPXTrace(filename)
		
		return trace

	def showGPXError(self,p):
                message_box = gtk.MessageDialog(parent=p,type=gtk.MESSAGE_ERROR,buttons=gtk.BUTTONS_OK,message_format=_("You selected an invalid GPX file. \n Please try again"))
                message_box.run()
                message_box.destroy()
                return None

		
	def quit(self,w):
		gtk.main_quit()
		
	def opengpx(self,w):
		self.trace = self.loadGPX()
		
		if self.trace == False:
			return None
		
		self.updateForNewFile()
	
	def zoomMapIn(self,w):
		self.map.zoom_in()
	
	def zoomMapOut(self,w):
		self.map.zoom_out()
		
	def addTrack(self,points):
		track = osmgpsmap.GpsMapTrack()
		for rlat,rlon in points:
			track.add_point(osmgpsmap.point_new_radians(rlat, rlon))
		self.map.track_add(track)
		
	def clearTrack(self):
		self.map.track_remove_all()
		
	def setCentre(self,lat,lon):
		self.map.set_center_and_zoom(lat,lon,self.zoom)
		
	def setDistanceLabel(self,distance="--"):
		self.wTree.get_object("labelDistance").set_markup(_("<b>Distance:</b> %s km") % distance)
		
	def setAverageSpeedLabel(self,average_speed="--"):
		self.wTree.get_object("labelAverageSpeed").set_markup(_("<b>Average Speed:</b> %s m/s") % average_speed)
		
	def setMaximumSpeedLabel(self,maximum_speed="--"):
		self.wTree.get_object("labelMaximumSpeed").set_markup(_("<b>Maximum Speed:</b> %s m/s") % maximum_speed)
		
	def setDurationLabel(self,minutes="--",seconds="--"):
		self.wTree.get_object("labelDuration").set_markup(_("<b>Duration:</b> %(minutes)s minutes, %(seconds)s seconds") % {"minutes": minutes, "seconds": seconds})
	
	def setLoggingDateLabel(self,gpxdate="--"):
		self.wTree.get_object("labelLoggingDate").set_markup(_("<b>Logging Date:</b> %s") % gpxdate)

	def setLoggingTimeLabel(self,gpxfrom="--",gpxto="--"):
		self.wTree.get_object("labelLoggingTime").set_markup(_("<b>Logging Time:</b> %(from)s - %(to)s") % {"from": gpxfrom, "to": gpxto})
