#  kate: space-indent off; indent-width 4; mixedindent off; indent-mode python;
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
import os
import sys
import traceback
import glib
import gtk
import gobject

import osmgpsmap
assert osmgpsmap.__version__ >= "0.7.1"

import stats

from gpx import GPXFile

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

def show_url(url):
	gtk.show_uri(None, url, gtk.gdk.CURRENT_TIME)

ALPHA_UNSELECTED = 0.5
ALPHA_SELECTED = 0.8
LAZY_LOAD_AFTER_N_FILES = 3
# List of track colors to rotate
TRACK_COLORS = ('#f00', '#00f', '#0f0', '#f0f', '#0ff', '#ff0')

class _TrackManager(gobject.GObject):

	NAME_IDX = 0
	FILENAME_IDX = 1

	__gsignals__ = {
		'track-added': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [object, object]),
		'track-removed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [object, object]),
    }

	def __init__(self):
		gobject.GObject.__init__(self)
		# maps track_filename : (GPXFile, [OsmGpsMapTrack])
		self._tracks = {}
		# name, filename
		self.model = gtk.ListStore(str, str)
		# Index of last used color
		self._lastColor = -1

	def getOtherTracks(self, trace):
		tracks = []
		for _trace,_tracks in self._tracks.values():
			if trace != _trace:
				tracks += _tracks
		return tracks

	def getTraceFromModel(self, _iter):
		filename = self.model.get_value(_iter, self.FILENAME_IDX)
		return self.getTrace(filename)

	def deleteTraceFromModel(self, _iter):
		self.emit("track-removed", *self._tracks[self.model.get_value(_iter, self.FILENAME_IDX)])
		self.model.remove(_iter)

	def getTrace(self, filename):
		""" Returns (trace, [OsmGpsMapTrack]) """
		return self._tracks[filename]

	def addTrace(self, trace):
		filename = trace.getFullPath()
		if filename not in self._tracks:
			gpstracks = []
			for track in trace.getTracks():
				# Rotate colors
				color = self._lastColor + 1
				if color >= len(TRACK_COLORS):
					color = 0
				self._lastColor = color
				
				for segment in track:
					gpstrack = osmgpsmap.GpsMapTrack()
					gpstrack.props.color = gtk.gdk.Color(TRACK_COLORS[color])
					gpstrack.props.alpha = ALPHA_UNSELECTED

					for point in segment:
						gpstrack.add_point(osmgpsmap.point_new_radians(point.getRadLat(), point.getRadLon()))
					gpstracks.append(gpstrack)

			self._tracks[filename] = (trace, gpstracks)
			self.model.append( (trace.getDisplayName(), filename) )
			self.emit("track-added", trace, gpstracks)

	def numTraces(self):
		return len(self._tracks)

	def getAllTraces(self):
		return [t[0] for t in self._tracks.values()]

class MainWindow:
	def __init__(self, ui_dir, files):
		# Will store here associations between file names and list of wpt images
		self._wptmap = {}
		
		self.localtz = LocalTimezone()
		self.recent = gtk.recent_manager_get_default()
		
		self.wTree = gtk.Builder()
		self.wTree.set_translation_domain('gpxviewer')
		self.wTree.add_from_file("%sgpxviewer.ui" % ui_dir)
		
		signals = {
			"on_windowMain_destroy": self.quit,
			"on_menuitemQuit_activate": self.quit,
			"on_menuitemOpen_activate": self.openGPX,
			"on_menuitemZoomIn_activate": self.zoomMapIn,
			"on_buttonZoomIn_clicked": self.zoomMapIn,
			"on_menuitemZoomOut_activate": self.zoomMapOut,
			"on_buttonZoomOut_clicked": self.zoomMapOut,
			"on_menuitemAbout_activate": self.openAboutDialog,
			"on_checkmenuitemShowSidebar_toggled": self.showSidebarToggled,
			"on_menuitemShowStatistics_activate": self.showStatistics,
			"on_buttonTrackAdd_clicked": self.buttonTrackAddClicked,
			"on_buttonTrackDelete_clicked": self.buttonTrackDeleteClicked,
			"on_buttonTrackInspect_clicked": self.buttonTrackInspectClicked,
		}
		
		self.mainWindow = self.wTree.get_object("windowMain")
		self.mainWindow.set_icon_from_file("%sgpxviewer.svg" % ui_dir)
		self.mainWindow.set_title(_("GPX Viewer"))

		i = self.wTree.get_object("checkmenuitemCenter")
		i.connect("toggled", self.autoCenterToggled)
		self.autoCenter = i.get_active()
		
		self.ui_dir = ui_dir

		self.map = osmgpsmap.GpsMap(
					tile_cache=os.path.join(
						glib.get_user_cache_dir(),
						'gpxviewer', 'tiles'))
		self.map.layer_add(
					osmgpsmap.GpsMapOsd(
						show_dpad=False,
						show_zoom=False,
						show_scale=True,
						show_coordinates=False))
		self.wTree.get_object("hbox_map").pack_start(self.map, True, True)

		sb = self.wTree.get_object("statusbar1")
		#move zoom control into apple like slider
		self.zoomSlider = MapZoomSlider(self.map)
		self.zoomSlider.show_all()
		a = gtk.Alignment(0.5,0.5,1.0,1.0)
		a.set_padding(0,0,0,4)
		a.add(self.zoomSlider)
		a.show_all()
		sb.pack_end(a, False, False, padding=4)

		#animate a spinner when downloading tiles
		try:
			self.spinner = gtk.Spinner()
			self.spinner.props.has_tooltip = True
			self.spinner.connect("query-tooltip", self.onSpinnerTooltip)
			self.map.connect("notify::tiles-queued", self.updateTilesQueued)
			self.spinner.set_size_request(*gtk.icon_size_lookup(gtk.ICON_SIZE_MENU))
			sb.pack_end(self.spinner, False, False)
		except AttributeError:
			self.spinner = None

		self.wTree.connect_signals(signals)
		
		#add open with external tool submenu items and actions
		programs = {
			'josm':N_('JOSM Editor'),
			'merkaartor':N_('Merkaartor'),
		}
		submenu_open_with = gtk.Menu() 
		for prog,progname in programs.iteritems():
			submenuitem_open_with = gtk.MenuItem(_(progname))
			submenu_open_with.append(submenuitem_open_with)
			submenuitem_open_with.connect("activate", self.openWithExternalApp, prog) 
			submenuitem_open_with.show()

		self.wTree.get_object('menuitemOpenBy').set_submenu(submenu_open_with)
		
		self.trackManager = _TrackManager()
		self.trackManager.connect("track-added", self.onTrackAdded)
		self.trackManager.connect("track-removed", self.onTrackRemoved)

		self.wTree.get_object("menuitemHelp").connect("activate", lambda *a: show_url("https://answers.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemTranslate").connect("activate", lambda *a: show_url("https://translations.launchpad.net/gpxviewer"))
		self.wTree.get_object("menuitemReportProblem").connect("activate", lambda *a: show_url("https://bugs.launchpad.net/gpxviewer/+filebug"))

		self.tv = gtk.TreeView(self.trackManager.model)
		self.tv.get_selection().connect("changed", self.onSelectionChanged)
		self.tv.append_column(
				gtk.TreeViewColumn(
					"Track Name",
					gtk.CellRendererText(),
					text=self.trackManager.NAME_IDX
				)
		)
		self.wTree.get_object("scrolledwindow1").add(self.tv)
		self.sb = self.wTree.get_object("vbox_sidebar")

		self.hideSpinner()
		self.hideTrackSelector()

		self.lazyLoadFiles(files)

		self.map.show()
		self.mainWindow.show()

	def lazyLoadFiles(self, files):
		def do_lazy_load(_files):
			try:
				self.loadGPX( _files.pop() )
				self.loadingFiles -= 1
				return True
			except IndexError:
				self.loadingFiles = 0
				return False

		self.loadingFiles = 0
		if not files:
			return

		#if less than LAZY_LOAD_AFTER_N_FILES load directly, else
		#load on idle
		if len(files) < LAZY_LOAD_AFTER_N_FILES:
			i = 0
			for filename in files:
				self.loadingFiles = i
				trace = self.loadGPX(filename)
				if i < LAZY_LOAD_AFTER_N_FILES:
					i += 1
				else:
					#select the last loaded trace
					self.loadingFiles = 0
					self.selectTrace(trace)
					break
		else:
			self.loadingFiles = len(files)
			gobject.timeout_add(100, do_lazy_load, files)

	def showSpinner(self):
		if self.spinner:
			self.spinner.show()
			self.spinner.start()

	def hideSpinner(self):
		if self.spinner:
			self.spinner.stop()
			self.spinner.hide()

	def onSpinnerTooltip(self, spinner, x, y, keyboard_mode, tooltip):
		tiles = self.map.props.tiles_queued
		if tiles:
			tooltip.set_text("Downloading Map")
			return True
		return False

	def showTrackSelector(self):
		self.sb.show_all()

	def hideTrackSelector(self):
		self.sb.hide_all()

	def onSelectionChanged(self, selection):
		model, _iter = selection.get_selected()
		if not _iter:
			return

		trace, tracks = self.trackManager.getTraceFromModel(_iter)
		self.selectTrace(trace)

		#highlight current track
		self.selectTracks(tracks, ALPHA_SELECTED)
		#dim other tracks
		self.selectTracks(self.trackManager.getOtherTracks(trace), ALPHA_UNSELECTED)

	def onTrackAdded(self, tm, trace, tracks):
		''' Called when a new GPX file has been loaded '''
		for t in tracks:
			self.map.track_add(t)
		self.selectTrace(trace)
		
		# Display waypoints from file
		for wpt in trace.getWaypoints():
			if wpt.lat != None and wpt.lon != None:
				pb = gtk.gdk.pixbuf_new_from_file_at_size("ui/wpt.png", 16,16)
				img = self.map.image_add(wpt.lat, wpt.lon, pb)
				if not trace.getFullPath() in self._wptmap.keys():
					self._wptmap[trace.getFullPath()] = []
				self._wptmap[trace.getFullPath()].append(img)

	def onTrackRemoved(self, tm, trace, tracks):
		for t in tracks:
			self.map.track_remove(t)
		# Remove waypoints
		if trace.getFullPath() in self._wptmap.keys():
			while len(self._wptmap[trace.getFullPath()]):
				img = self._wptmap[trace.getFullPath()].pop()
				self.map.image_remove(img)
			del self._wptmap[trace.getFullPath()]

	def updateTilesQueued(self, map_, paramspec):
		if self.map.props.tiles_queued > 0:
			self.showSpinner()
		else:
			self.hideSpinner()

	def showSidebarToggled(self, item):
		if item.get_active():
			self.showTrackSelector()
		else:
			self.hideTrackSelector()

	def showStatistics(self, item):
		ws = stats.WeekStats()
		ss = stats.AvgSpeedStats()
		for t in self.trackManager.getAllTraces():
			ws.addTrace(t)
			ss.addTrace(t)

		w = gtk.Window()
		w.add(stats.ChartNotebook(ws,ss))
		w.resize(500,300)
		w.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		w.set_transient_for(self.mainWindow)
		w.show_all()
	
	def openAboutDialog(self,w):
		dialog = self.wTree.get_object("dialogAbout")
		self.wTree.get_object("dialogAbout").set_icon_from_file("%sgpxviewer.svg" % self.ui_dir)
		dialog.connect("response", lambda *a: dialog.hide())
		dialog.show_all()

	def selectTracks(self, tracks, alpha):
		for t in tracks:
			t.props.alpha = alpha

	def selectTrace(self, trace):
		if self.loadingFiles:
			return

		self.zoom = 12
		distance = trace.getDistance()
		maximum_speed = trace.getMaximumSpeed()
		average_speed = trace.getAverageSpeed()
		duration = trace.getDuration()
		clat, clon = trace.getCentre()
		gpxfrom = trace.getGpxFrom().astimezone(self.localtz)
		gpxto = trace.getGpxTo().astimezone(self.localtz)

		self.setDistanceLabel(round(distance/1000,2))
		self.setMaximumSpeedLabel(maximum_speed)
		self.setAverageSpeedLabel(average_speed)
		self.setDurationLabel(int(duration/60),duration-(int(duration/60)*60))
		self.setLoggingDateLabel(gpxfrom.strftime("%x"))
		self.setLoggingTimeLabel(gpxfrom.strftime("%X"),gpxto.strftime("%X"))

		self.currentFilename = trace.getFilename()
		self.mainWindow.set_title(_("GPX Viewer - %s") % trace.getFilename())

		if self.autoCenter:
			self.setCentre(clat,clon)

	def loadGPX(self, filename):
		try:
			trace = GPXFile(filename)
			self.trackManager.addTrace(trace)
			if self.trackManager.numTraces() > 1:
				self.showTrackSelector()
			return trace
		except Exception, e:
			print 'Error loading file:', e
			traceback.print_exc()
			self.showGPXError()
			return None

	def openGPX(self, *args):
		filechooser = gtk.FileChooserDialog(title=_("Choose a GPX file to Load"),action=gtk.FILE_CHOOSER_ACTION_OPEN,parent=self.mainWindow)
		filechooser.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_DELETE_EVENT)
		filechooser.add_button(gtk.STOCK_OPEN, gtk.RESPONSE_OK)
		filechooser.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		response = filechooser.run()
		filename = filechooser.get_filename()
		
		if response == gtk.RESPONSE_OK:
			if self.loadGPX(filename):
				self.recent.add_item("file://"+filename)

		filechooser.destroy()

	def showGPXError(self):
		message_box = gtk.MessageDialog(parent=self.mainWindow,type=gtk.MESSAGE_ERROR,buttons=gtk.BUTTONS_OK,message_format=_("You selected an invalid GPX file. \n Please try again"))
		message_box.run()
		message_box.destroy()
		return None

	def quit(self,w):
		gtk.main_quit()

	def main(self):
		gtk.main()

	def openWithExternalApp(self,w,app):
		if self.currentFilename:
			os.spawnlp(os.P_NOWAIT,app,app,self.currentFilename)
 	
	def zoomMapIn(self,w):
		self.map.zoom_in()
	
	def zoomMapOut(self,w):
		self.map.zoom_out()
		
	def setCentre(self,lat,lon):
		self.map.set_center_and_zoom(lat,lon,self.zoom)
		
	def setDistanceLabel(self,distance="--"):
		self.wTree.get_object("labelDistance").set_markup(_("<b>Distance:</b> %.2f km") % distance)
		
	def setAverageSpeedLabel(self,average_speed="--"):
		self.wTree.get_object("labelAverageSpeed").set_markup(_("<b>Average Speed:</b> %.2f m/s") % average_speed)
		
	def setMaximumSpeedLabel(self,maximum_speed="--"):
		self.wTree.get_object("labelMaximumSpeed").set_markup(_("<b>Maximum Speed:</b> %.2f m/s") % maximum_speed)
		
	def setDurationLabel(self,minutes="--",seconds="--"):
		self.wTree.get_object("labelDuration").set_markup(_("<b>Duration:</b> %(minutes)s minutes, %(seconds)s seconds") % {"minutes": minutes, "seconds": seconds})
	
	def setLoggingDateLabel(self,gpxdate="--"):
		self.wTree.get_object("labelLoggingDate").set_markup(_("<b>Logging Date:</b> %s") % gpxdate)

	def setLoggingTimeLabel(self,gpxfrom="--",gpxto="--"):
		self.wTree.get_object("labelLoggingTime").set_markup(_("<b>Logging Time:</b> %(from)s - %(to)s") % {"from": gpxfrom, "to": gpxto})

	def autoCenterToggled(self, item):
		self.autoCenter = item.get_active()

	def buttonTrackAddClicked(self, *args):
		self.openGPX()

	def buttonTrackDeleteClicked(self, *args):
		model, _iter = self.tv.get_selection().get_selected()
		if _iter:
			self.trackManager.deleteTraceFromModel(_iter)

	def buttonTrackInspectClicked(self, *args):
		pass

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
