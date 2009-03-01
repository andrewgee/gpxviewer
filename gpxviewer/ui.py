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
import sys
try: 
   import pygtk 
   pygtk.require("2.0") 
except: 
   pass 
try: 
   import gtk 
   import gtk.glade 
except: 
   print "GTK is not installed" 
   sys.exit(1) 

import osmgpsmap
from gpx import GPXTrace, check_file

try:
	import gnome
	def show_url(url): gnome.url_show(url)
except:
	import os
	def show_url(url): os.system("xdg-open %s" % url)

import gettext
_ = gettext.lgettext

class MainWindow:
	def __init__(self,ui_dir="ui/",filename=None):
		self.wTree = gtk.glade.XML("%sgps.glade" % ui_dir)
		signals = {
			"on_windowMain_destroy": self.quit,
			"on_menuitemQuit_activate": self.quit,
			"on_menuitemOpen_activate": self.opengpx,
			"on_buttonZoomIn_clicked": self.zoomMapIn,
			"on_buttonZoomOut_clicked": self.zoomMapOut,
			"on_menuitemAbout_activate": self.openAboutDialog,
		}
		
		self.wTree.get_widget("windowMain").set_icon_from_file("%sgpxviewer.svg" % ui_dir)
		
		self.ui_dir = ui_dir
		
		self.map = osmgpsmap.GpsMap()
		self.wTree.get_widget("vbox3").add(self.map)
		self.wTree.get_widget("vbox3").reorder_child(self.map, 0)
		
		self.wTree.signal_autoconnect(signals)
		
		self.wTree.get_widget("windowMain").show_all()
		self.wTree.get_widget("windowMain").set_title(_("GPX Viewer"))
		
		self.wTree.get_widget("menuitemHelp").connect("activate", lambda *a: show_url("https://answers.launchpad.net/gpxviewer"))
		self.wTree.get_widget("menuitemTranslate").connect("activate", lambda *a: show_url("https://translations.launchpad.net/gpxviewer"))
		self.wTree.get_widget("menuitemReportProblem").connect("activate", lambda *a: show_url("https://bugs.launchpad.net/gpxviewer/+filebug"))
	
	def openAboutDialog(self,w):
		dialog = self.wTree.get_widget("dialogAbout")
		self.wTree.get_widget("dialogAbout").set_icon_from_file("%sgpxviewer.svg" % self.ui_dir)
		dialog.connect("response", lambda *a: dialog.hide())
		dialog.show_all()
		
	def updateForNewFile(self):
		self.zoom = 12
		
		distance = self.trace.get_distance()
		maximum_speed = self.trace.get_maximum_speed()
		average_speed = self.trace.get_average_speed()
		duration = self.trace.get_duration()
		segments = self.trace.get_points()
		clat, clon = self.trace.get_centre()
		
		self.setDistanceLabel(round(distance/1000,2))
		self.setMaximumSpeedLabel(maximum_speed)
		self.setAverageSpeedLabel(average_speed)
		self.setDurationLabel(int(duration/60),duration-(int(duration/60)*60))
		self.setCentre(clat,clon)
		
		self.clearTrack()
		
		for segment in segments:
			self.addTrack(segment)
		
		self.wTree.get_widget("windowMain").set_title(_("GPX Viewer - %s" % self.trace.get_filename()))
			
	def loadGPX(self, filename=None):
		if filename == None:
			result = None
			while result == None:
				result = self.chooseGPX()
			if result == False:
				return False
		
		return result
		
	def chooseGPX(self):
		filechooser = gtk.FileChooserDialog(title=_("Choose a GPX file to Load"),action=gtk.FILE_CHOOSER_ACTION_OPEN,parent=self.wTree.get_widget("windowMain"))
		filechooser.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_DELETE_EVENT)
		filechooser.add_button(gtk.STOCK_OPEN, gtk.RESPONSE_OK)
		filechooser.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		response = filechooser.run()
		filename = filechooser.get_filename()
		
		if response == gtk.RESPONSE_DELETE_EVENT:
			filechooser.destroy()
			return False
		
		if check_file(filename) != True:
			message_box = gtk.MessageDialog(parent=filechooser,type=gtk.MESSAGE_ERROR,buttons=gtk.BUTTONS_OK,message_format=_("You selected an invalid GPX file. \n Please try again"))
			message_box.run()
			message_box.destroy()
			filechooser.destroy()		
			return None
		
		filechooser.destroy()
		
		trace = GPXTrace(filename)
		
		return trace
		
	def quit(self,w):
		gtk.main_quit()
		
	def opengpx(self,w):
		self.trace = self.loadGPX()
		
		if self.trace == False:
			return None
		
		self.updateForNewFile()
	
	def zoomMapIn(self,w):
		zoom = self.map.get_property("zoom")
		self.map.set_zoom(zoom + 1)
	
	def zoomMapOut(self,w):
		zoom = self.map.get_property("zoom")
		self.map.set_zoom(zoom - 1)
		
	def addTrack(self,points):
		self.map.add_track(points)
		
	def clearTrack(self):
		self.map.clear_tracks()
		
	def setCentre(self,lat,lon):
		self.map.set_mapcenter(lat,lon,self.zoom)
		
	def setDistanceLabel(self,distance="--"):
		self.wTree.get_widget("labelDistance").set_markup(_("<b>Distance:</b> %s km" % distance))
		
	def setAverageSpeedLabel(self,average_speed="--"):
		self.wTree.get_widget("labelAverageSpeed").set_markup(_("<b>Average Speed:</b> %s m/s" % average_speed))
		
	def setMaximumSpeedLabel(self,maximum_speed="--"):
		self.wTree.get_widget("labelMaximumSpeed").set_markup(_("<b>Maximum Speed:</b> %s m/s" % maximum_speed))
		
	def setDurationLabel(self,minutes="--",seconds="--"):
		self.wTree.get_widget("labelDuration").set_markup(_("<b>Duration:</b> %(minutes)s minutes, %(seconds)s seconds" % {"minutes": minutes, "seconds": seconds}))
