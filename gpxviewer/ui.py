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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from gi.repository import OsmGpsMap

import stats

from gpx import GPXTrace

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
	Gtk.show_uri(None, url, Gdk.CURRENT_TIME)

ALPHA_UNSELECTED = 0.5
ALPHA_SELECTED = 0.8
LAZY_LOAD_AFTER_N_FILES = 3

class _TrackManager(GObject.GObject):

	NAME_IDX = 0
	FILENAME_IDX = 1

	__gsignals__ = {
		'track-added': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, [object, object]),
		'track-removed': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, [object, object]),
    }

	def __init__(self):
		GObject.GObject.__init__(self)
		# maps track_filename : (GPXTrace, [OsmGpsMapTrack])
		self._tracks = {}
		# name, filename
		self.model = Gtk.ListStore(str, str)

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
		filename = trace.get_full_path()
		if filename not in self._tracks:
			gpstracks = []
			for track in trace.get_points():
			  for segment in track:

				gpstrack = OsmGpsMap.MapTrack()				
				gpstrack.props.alpha = 0.8

				for rlat,rlon in segment:
					gpstrack.add_point(OsmGpsMap.MapPoint.new_radians(rlat, rlon))
				gpstracks.append(gpstrack)

			self._tracks[filename] = (trace, gpstracks)
			self.model.append( (trace.get_display_name(), filename) )
			self.emit("track-added", trace, gpstracks)

	def numTraces(self):
		return len(self._tracks)

	def getAllTraces(self):
		return [t[0] for t in self._tracks.values()]

class MainWindow:
	def __init__(self, ui_dir, files):
		self.localtz = LocalTimezone()
		self.recent = Gtk.RecentManager.get_default()
		
		self.wTree = Gtk.Builder()
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
			"on_buttonTrackProperties_clicked": self.buttonTrackPropertiesClicked,
			"on_buttonTrackInspect_clicked": self.buttonTrackInspectClicked,
		}
		
		self.mainWindow = self.wTree.get_object("windowMain")
		self.mainWindow.set_icon_from_file("%sgpxviewer.svg" % ui_dir)
		self.mainWindow.set_title(_("GPX Viewer"))

		i = self.wTree.get_object("checkmenuitemCenter")
		i.connect("toggled", self.autoCenterToggled)
		self.autoCenter = i.get_active()
		
		self.ui_dir = ui_dir

		self.map = OsmGpsMap.Map(
					tile_cache=os.path.join(
						GLib.get_user_cache_dir(),
						'gpxviewer', 'tiles'))
		self.map.layer_add(
					OsmGpsMap.MapOsd(
						show_dpad=False,
						show_zoom=False,
						show_scale=True,
						show_coordinates=False))
		self.wTree.get_object("hbox_map").pack_start(self.map, True, True, 0)

		sb = self.wTree.get_object("statusbar1")
		#move zoom control into apple like slider
		self.zoomSlider = MapZoomSlider(self.map)
		self.zoomSlider.show_all()
		a = Gtk.Alignment.new(0.5,0.5,1.0,1.0)
		a.set_padding(0,0,0,4)
		a.add(self.zoomSlider)
		a.show_all()
		sb.pack_end(a, False, False, padding=4)

		#animate a spinner when downloading tiles
		try:
			self.spinner = Gtk.Spinner()
			self.spinner.props.has_tooltip = True
			self.spinner.connect("query-tooltip", self.onSpinnerTooltip)
			self.map.connect("notify::tiles-queued", self.updateTilesQueued)
			self.spinner.set_size_request(*Gtk.icon_size_lookup(Gtk.ICON_SIZE_MENU))
			sb.pack_end(self.spinner, False, False)
		except AttributeError:
			self.spinner = None

		self.wTree.connect_signals(signals)
		
		#add open with external tool submenu items and actions
		programs = {
			'josm':N_('JOSM Editor'),
			'merkaartor':N_('Merkaartor'),
		}
		submenu_open_with = Gtk.Menu() 
		for prog,progname in programs.iteritems():
			submenuitem_open_with = Gtk.MenuItem(_(progname))
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

		self.tv = Gtk.TreeView(self.trackManager.model)
		self.tv.get_selection().connect("changed", self.onSelectionChanged)
		self.tv.append_column(
				Gtk.TreeViewColumn(
					"Track Name",
					Gtk.CellRendererText(),
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
			GObject.timeout_add(100, do_lazy_load, files)

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
		self.sb.hide()

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
		for t in tracks:
			self.map.track_add(t)
		self.selectTrace(trace)

	def onTrackRemoved(self, tm, trace, tracks):
		for t in tracks:
			self.map.track_remove(t)

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

		w = Gtk.Window()
		w.add(stats.ChartNotebook(ws,ss))
		w.resize(500,300)
		w.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
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

		self.currentFilename = trace.get_filename()
		self.mainWindow.set_title(_("GPX Viewer - %s") % trace.get_filename())

		if self.autoCenter:
			self.setCentre(clat,clon)

	def loadGPX(self, filename):
		try:
			trace = GPXTrace(filename)
			self.trackManager.addTrace(trace)
			if self.trackManager.numTraces() > 1:
				self.showTrackSelector()
			return trace
		except Exception, e:
			self.showGPXError()
			return None

	def openGPX(self, *args):
		filechooser = Gtk.FileChooserDialog(title=_("Choose a GPX file to Load"),action=Gtk.FileChooserAction.OPEN,parent=self.mainWindow)
		filechooser.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.DELETE_EVENT)
		filechooser.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		filechooser.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
		filechooser.set_select_multiple(True)
		response = filechooser.run()
		
		if response == Gtk.ResponseType.OK:
			for filename in filechooser.get_filenames():
				if self.loadGPX(filename):
					self.recent.add_item("file://"+filename)

		filechooser.destroy()

	def showGPXError(self):
		message_box = Gtk.MessageDialog(parent=self.mainWindow,type=Gtk.MESSAGE_ERROR,buttons=Gtk.BUTTONS_OK,message_format=_("You selected an invalid GPX file. \n Please try again"))
		message_box.run()
		message_box.destroy()
		return None

	def quit(self,w):
		Gtk.main_quit()

	def main(self):
		Gtk.main()

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

	def buttonTrackPropertiesClicked(self, *args):
		model, _iter = self.tv.get_selection().get_selected()
		if _iter:
			trace, OsmGpsMapTracks = self.trackManager.getTraceFromModel(_iter)
			colorseldlg = Gtk.ColorSelectionDialog("Select track color")
			colorseldlg.get_color_selection().set_current_color(OsmGpsMapTracks[0].props.color)
			result = colorseldlg.run()
			if result == Gtk.ResponseType.OK:
				color = colorseldlg.get_color_selection().get_current_rgba()
				print color
				for OsmGpsMapTrack in OsmGpsMapTracks:
					OsmGpsMapTrack.set_color(color)
					self.map.map_redraw()
			colorseldlg.destroy()

	def buttonTrackInspectClicked(self, *args):
		pass

class MapZoomSlider(Gtk.HBox):
    def __init__(self, _map):
        Gtk.HBox.__init__(self)

        zo = Gtk.EventBox()
        zo.add(Gtk.Image.new_from_stock (Gtk.STOCK_ZOOM_OUT, Gtk.IconSize.MENU))
        zo.connect("button-press-event", self._on_zoom_out_pressed, _map)
        self.pack_start(zo, False, False, 0)

        self.zoom = Gtk.Adjustment(
                            value=_map.props.zoom,
                            lower=_map.props.min_zoom,
                            upper=_map.props.max_zoom,
                            step_incr=1,
                            page_incr=1,
                            page_size=0)
        self.zoom.connect("value-changed", self._on_zoom_slider_value_changed, _map)
        hs = Gtk.HScale()
        hs.set_adjustment(self.zoom)
        hs.props.digits = 0
        hs.props.draw_value = False
        hs.set_size_request(100,-1)
        #hs.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        self.pack_start(hs, True, True, 0)

        zi = Gtk.EventBox()
        zi.add(Gtk.Image.new_from_stock (Gtk.STOCK_ZOOM_IN, Gtk.IconSize.MENU))
        zi.connect("button-press-event", self._on_zoom_in_pressed, _map)
        self.pack_start(zi, False, False, 0)

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
