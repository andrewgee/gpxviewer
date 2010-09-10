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
   pygtk.require("2.20") 
except: 
   pass 
try: 
   import gtk 
except: 
   print "GTK is not installed" 
   sys.exit(1) 

import gobject

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

# Function used to defer translation until later, while still being recognised 
# by build_i18n
def N_(message): 
  return message

ALPHA_UNSELECTED = 0.5
ALPHA_SELECTED = 0.8

class _TrackManager(gobject.GObject):

	NAME_IDX = 0
	FILENAME_IDX = 1

	__gsignals__ = {
		'track-added': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [str]),
    }

	def __init__(self):
		gobject.GObject.__init__(self)
		# maps track_filename : (GPXTrace, [OsmGpsMapTrack])
		self._tracks = {}
		# name, filename
		self.model = gtk.ListStore(str, str)

	def getTrace(self, filename):
		""" Returns (trace, [OsmGpsMapTrack]) """
		return self._tracks[filename]

	def addTrace(self, trace):
		filename = trace.get_full_path()
		if filename not in self._tracks:
			gpstracks = []
			for track in trace.get_points():
			  for segment in track:

				gpstrack = osmgpsmap.GpsMapTrack()
				gpstrack.props.alpha = ALPHA_UNSELECTED

				for rlat,rlon in segment:
					gpstrack.add_point(osmgpsmap.point_new_radians(rlat, rlon))
				gpstracks.append(gpstrack)

			self._tracks[filename] = (trace, gpstracks)
			self.model.append( (trace.get_display_name(), filename) )

			self.emit("track-added", filename)

class MainWindow:
	def __init__(self,ui_dir="ui/",filename=None):
		self.localtz = LocalTimezone()
		
		self.wTree = gtk.Builder()
		self.wTree.set_translation_domain('gpxviewer')
		self.wTree.add_from_file("%sgpxviewer.ui" % ui_dir)
		
		signals = {
			"on_windowMain_destroy": self.quit,
			"on_menuitemQuit_activate": self.quit,
			"on_menuitemOpen_activate": self.loadGPX,
			"on_menuitemZoomIn_activate": self.zoomMapIn,
			"on_buttonZoomIn_clicked": self.zoomMapIn,
			"on_menuitemZoomOut_activate": self.zoomMapOut,
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

		sb = self.wTree.get_object("statusbar1")
		#move zoom control into apple like slider
		self.zoomSlider = MapZoomSlider(self.map)
		self.zoomSlider.show_all()
		sb.pack_end(self.zoomSlider, False, False)

		#animate a spinner when downloading tiles
		self.spinner = gtk.Spinner()
		self.map.connect("notify::tiles-queued", self.updateTilesQueued)
		self.spinner.set_size_request(*gtk.icon_size_lookup(gtk.ICON_SIZE_MENU))
		sb.pack_end(self.spinner, False, False)

		self.wTree.get_object("hbox_map").pack_start(self.map, True, True)
		
		self.wTree.connect_signals(signals)
		
		self.wTree.get_object("windowMain").show_all()
		self.wTree.get_object("windowMain").set_title(_("GPX Viewer"))

		#add openby submenu items and actions
		programs = {
			'josm':N_('JOSM Editor'),
			'merkaartor':N_('Merkaartor'),
		}
		submenu_openby = gtk.Menu() 
		for prog,progname in programs.iteritems():
			submenuitem_openby = gtk.MenuItem(_(progname))
			submenu_openby.append(submenuitem_openby)
			submenuitem_openby.connect("activate", self.openby, prog) 
			submenuitem_openby.show()

		self.wTree.get_object('menuitemOpenBy').set_submenu(submenu_openby)
		
		self.trackManager = _TrackManager()
		self.trackManager.connect("track-added", self.onTrackAdded)

		if filename != None:
			self.loadGPX(filename=filename)
		
		self.wTree.get_object("menuitemHelp").connect("activate", lambda *a: show_url("https://answers.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemTranslate").connect("activate", lambda *a: show_url("https://translations.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemReportProblem").connect("activate", lambda *a: show_url("https://bugs.launchpad.net/gpxviewer/+filebug"))

		tv = gtk.TreeView(self.trackManager.model)
		tv.append_column(
			gtk.TreeViewColumn("Track Name", gtk.CellRendererText(), text=0))
		self.wTree.get_object("hbox1").pack_start(tv, False, True)
		tv.show_all()

		self.spinner.hide()

	def onTrackAdded(self, tm, filename):
		trace, tracks = self.trackManager.getTrace(filename)
		for t in tracks:
			self.map.track_add(t)
		self.selectTrace(trace)

	def updateTilesQueued(self, map_, paramspec):
		if self.map.props.tiles_queued > 0:
			self.spinner.show()
			self.spinner.start()
		else:
			self.spinner.stop()
			self.spinner.hide()
	
	def openAboutDialog(self,w):
		dialog = self.wTree.get_object("dialogAbout")
		self.wTree.get_object("dialogAbout").set_icon_from_file("%sgpxviewer.svg" % self.ui_dir)
		dialog.connect("response", lambda *a: dialog.hide())
		dialog.show_all()

	def selectTrace(self, trace):
		self.zoom = 12

		distance = trace.get_distance()
		maximum_speed = trace.get_maximum_speed()
		average_speed = trace.get_average_speed()
		duration = trace.get_duration()
		clat, clon = trace.get_centre()
		gpxfrom = trace.get_gpxfrom().astimezone(self.localtz)
		gpxto = trace.get_gpxto().astimezone(self.localtz)
		
		self.setDistanceLabel(round(distance/1000,2))
		self.setMaximumSpeedLabel(maximum_speed)
		self.setAverageSpeedLabel(average_speed)
		self.setDurationLabel(int(duration/60),duration-(int(duration/60)*60))
		self.setLoggingDateLabel(gpxfrom.strftime("%x"))
		self.setLoggingTimeLabel(gpxfrom.strftime("%X"),gpxto.strftime("%X"))
		self.setCentre(clat,clon)
		
		self.currentFilename = trace.get_filename()

		self.wTree.get_object("windowMain").set_title(_("GPX Viewer - %s") % trace.get_filename())
		
	def loadGPX(self, *args, **kwargs): 
		result = None
		filename = kwargs.get("filename")
		if filename == None:
			while result == None:
				result = self.chooseGPX()
			if result == False:
				return
		else:
			if check_file(filename) != True:
				self.showGPXError(None)
				return
			else:
				result = GPXTrace(filename)

		if result:
			self.trackManager.addTrace(result)

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

	def openby(self,w,app):
		try: self.currentFilename
		except AttributeError:
			return
		else:
			filepath = self.currentFilename
			pid = os.spawnlp(os.P_NOWAIT,app,app,filepath)
 	
	def zoomMapIn(self,w):
		self.map.zoom_in()
	
	def zoomMapOut(self,w):
		self.map.zoom_out()
		
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

class MapZoomSlider(gtk.HBox):
    def __init__(self, _map):
        gtk.HBox.__init__(self)

        zo = gtk.EventBox()
        zo.add(gtk.image_new_from_stock (gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_MENU))
        zo.connect("button-press-event", self._on_zoom_out_pressed, _map)
        self.pack_start(zo, False, False)

        self.zoom = gtk.Adjustment(
                            value=_map.props.zoom,
                            lower=_map.props.min_zoom,
                            upper=_map.props.max_zoom,
                            step_incr=1,
                            page_incr=1,
                            page_size=0)
        self.zoom.connect("value-changed", self._on_zoom_slider_value_changed, _map)
        hs = gtk.HScale(self.zoom)
        hs.props.digits = 0
        hs.props.draw_value = False
        hs.set_size_request(100,-1)
        hs.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        self.pack_start(hs, True, True)

        zi = gtk.EventBox()
        zi.add(gtk.image_new_from_stock (gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_MENU))
        zi.connect("button-press-event", self._on_zoom_in_pressed, _map)
        self.pack_start(zi, False, False)

        _map.connect("notify::zoom", self._on_map_zoom_changed)

    def _on_zoom_in_pressed(self, box, event, _map):
        _map.zoom_in()

    def _on_zoom_out_pressed(self, box, event, _map):
        _map.zoom_out()

    def _on_zoom_slider_value_changed(self, adj, _map):
        zoom = adj.get_value()
        if zoom != _map.props.zoom:
            _map.set_zoom( int(zoom) )

    def _on_map_zoom_changed(self, _map, paramspec):
        self.zoom.set_value(_map.props.zoom)
