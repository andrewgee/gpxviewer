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

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('OsmGpsMap', '1.0')

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from gi.repository import OsmGpsMap

from . import stats

from gpxpy import parse
from gpxpy.gpx import GPXException
from colorsys import hsv_to_rgb

import locale
import gettext

locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain('gpxviewer')
gettext.textdomain('gpxviewer')
_ = gettext.gettext


# Function used to defer translation until later, while still being recognised
# by build_i18n
def N_(message):
    return message


def show_url(url):
    Gtk.show_uri(None, url, Gdk.CURRENT_TIME)


ALPHA_UNSELECTED = 0.5
ALPHA_SELECTED = 0.8
LAZY_LOAD_AFTER_N_FILES = 3


class MainWindow:
    NAME_IDX = 0
    GPX_IDX = 1
    OSM_IDX = 2

    def get_other_tracks(self, trace):
        tracks = []
        for row in self.model:
            for track in row.iterchildren():
                if trace != track[self.GPX_IDX]:
                    tracks += track[self.OSM_IDX]
        return tracks

    def add_track(self, parent, track, color):
        gpstracks = []
        for segment in track.segments:

            gpstrack = OsmGpsMap.MapTrack()
            gpstrack.set_color(color)
            gpstrack.props.alpha = 0.8

            for point in segment.points:
                gpstrack.add_point(OsmGpsMap.MapPoint.new_degrees(point.latitude, point.longitude))

            gpstracks.append(gpstrack)
            self.map.track_add(gpstrack)

        self.model.append(parent, [track.name, track, gpstracks])

    def get_all_traces(self):
        return [t[self.GPX_IDX] for f in self.model for t in f.iterchildren()]

    def __init__(self, ui_dir, files):
        self.recent = Gtk.RecentManager.get_default()

        self.wTree = Gtk.Builder()
        self.wTree.set_translation_domain('gpxviewer')
        self.wTree.add_from_file("%sgpxviewer.ui" % ui_dir)

        # track_name, gpx, [OsmGpsMapTrack]
        self.model = Gtk.TreeStore(str, object, object)

        signals = {
            "on_windowMain_destroy": self.quit,
            "on_menuitemQuit_activate": self.quit,
            "on_menuitemOpen_activate": self.open_gpx,
            "on_menuitemZoomIn_activate": self.zoom_map_in,
            "on_buttonZoomIn_clicked": self.zoom_map_in,
            "on_menuitemZoomOut_activate": self.zoom_map_out,
            "on_buttonZoomOut_clicked": self.zoom_map_out,
            "on_menuitemAbout_activate": self.open_about_dialog,
            "on_checkmenuitemShowSidebar_toggled": self.show_sidebar_toggled,
            "on_menuitemShowStatistics_activate": self.show_statistics,
            "on_buttonTrackAdd_clicked": self.button_track_add_clicked,
            "on_buttonTrackDelete_clicked": self.button_track_delete_clicked,
            "on_buttonTrackProperties_clicked": self.button_track_properties_clicked,
            "on_buttonTrackInspect_clicked": self.button_track_inspect_clicked,
        }

        self.mainWindow = self.wTree.get_object("windowMain")
        self.mainWindow.set_icon_from_file("%sgpxviewer.svg" % ui_dir)
        self.mainWindow.set_title(_("GPX Viewer"))

        i = self.wTree.get_object("checkmenuitemCenter")
        i.connect("toggled", self.auto_center_toggled)
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
        # move zoom control into apple like slider
        self.zoomSlider = MapZoomSlider(self.map)
        self.zoomSlider.show_all()
        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        a.set_padding(0, 0, 0, 4)
        a.add(self.zoomSlider)
        a.show_all()
        sb.pack_end(a, False, False, padding=4)

        # animate a spinner when downloading tiles
        try:
            self.spinner = Gtk.Spinner()
            self.spinner.props.has_tooltip = True
            self.spinner.connect("query-tooltip", self.on_spinner_tooltip)
            self.map.connect("notify::tiles-queued", self.update_tiles_queued)
            self.spinner.set_size_request(*Gtk.icon_size_lookup(Gtk.IconSize.MENU)[:2])
            sb.pack_end(self.spinner, False, False, 0)
        except AttributeError:
            self.spinner = None

        self.wTree.connect_signals(signals)

        # add open with external tool submenu items and actions
        programs = {
            'josm': N_('JOSM Editor'),
            'merkaartor': N_('Merkaartor'),
        }
        submenu_open_with = Gtk.Menu()
        for prog, progname in programs.items():
            submenuitem_open_with = Gtk.MenuItem(_(progname))
            submenu_open_with.append(submenuitem_open_with)
            submenuitem_open_with.connect("activate", self.open_with_external_app, prog)
            submenuitem_open_with.show()

        self.wTree.get_object('menuitemOpenBy').set_submenu(submenu_open_with)

        self.wTree.get_object("menuitemHelp").connect("activate",
                                                      lambda *a: show_url("https://answers.launchpad.net/gpxviewer"))
        self.wTree.get_object("menuitemTranslate").connect("activate", lambda *a: show_url(
            "https://translations.launchpad.net/gpxviewer"))
        self.wTree.get_object("menuitemReportProblem").connect("activate", lambda *a: show_url(
            "https://bugs.launchpad.net/gpxviewer/+filebug"))

        self.tv = Gtk.TreeView(self.model)
        self.tv.get_selection().connect("changed", self.on_selection_changed)
        self.tv.append_column(
            Gtk.TreeViewColumn(
                "Track Name",
                Gtk.CellRendererText(),
                text=self.NAME_IDX
            )
        )
        self.wTree.get_object("scrolledwindow1").add(self.tv)
        self.sb = self.wTree.get_object("vbox_sidebar")

        self.hide_spinner()
        self.hide_track_selector()

        self.lazyLoadFiles(files)

        self.map.show()
        self.mainWindow.show()

    def lazyLoadFiles(self, files):
        def do_lazy_load(_files):
            try:
                self.load_gpx(_files.pop())
                self.loadingFiles -= 1
                return True
            except IndexError:
                self.loadingFiles = 0
                return False

        self.loadingFiles = 0
        if not files:
            return

        # if less than LAZY_LOAD_AFTER_N_FILES load directly, else
        # load on idle
        if len(files) < LAZY_LOAD_AFTER_N_FILES:
            i = 0
            for filename in files:
                self.loadingFiles = i
                self.load_gpx(filename)
                if i < LAZY_LOAD_AFTER_N_FILES:
                    i += 1
                else:
                    self.loadingFiles = 0
                    break
        else:
            self.loadingFiles = len(files)
            GObject.timeout_add(100, do_lazy_load, files)

    def show_spinner(self):
        if self.spinner:
            self.spinner.show()
            self.spinner.start()

    def hide_spinner(self):
        if self.spinner:
            self.spinner.stop()
            self.spinner.hide()

    def on_spinner_tooltip(self, spinner, x, y, keyboard_mode, tooltip):
        tiles = self.map.props.tiles_queued
        if tiles:
            tooltip.set_text("Downloading Map")
            return True
        return False

    def show_track_selector(self):
        self.sb.show_all()

    def hide_track_selector(self):
        self.sb.hide()

    def on_selection_changed(self, selection):
        model, _iter = selection.get_selected()
        if not _iter:
            return

        trace = self.model.get_value(_iter, self.GPX_IDX)
        tracks = self.model.get_value(_iter, self.OSM_IDX)
        self.select_trace(self.model[_iter])

        # highlight current track
        self.select_tracks(tracks, ALPHA_SELECTED)
        # dim other tracks
        self.select_tracks(self.get_other_tracks(trace), ALPHA_UNSELECTED)

    def update_tiles_queued(self, map_, paramspec):
        if self.map.props.tiles_queued > 0:
            self.show_spinner()
        else:
            self.hide_spinner()

    def show_sidebar_toggled(self, item):
        if item.get_active():
            self.show_track_selector()
        else:
            self.hide_track_selector()

    def show_statistics(self, item):
        ws = stats.WeekStats()
        ss = stats.AvgSpeedStats()
        for t in self.get_all_traces():
            ws.addTrace(t)
            ss.addTrace(t)

        w = Gtk.Window()
        w.add(stats.ChartNotebook(ws, ss))
        w.resize(500, 300)
        w.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        w.set_transient_for(self.mainWindow)
        w.show_all()

    def open_about_dialog(self, w):
        dialog = self.wTree.get_object("dialogAbout")
        self.wTree.get_object("dialogAbout").set_icon_from_file("%sgpxviewer.svg" % self.ui_dir)
        dialog.connect("response", lambda *a: dialog.hide())
        dialog.show_all()

    def select_tracks(self, tracks, alpha):
        if not tracks:
            return
        for t in tracks:
            t.props.alpha = alpha

    def select_trace(self, row):
        if not row[self.GPX_IDX]:
            self.set_distance_label()
            self.set_maximum_speed_label()
            self.set_average_speed_label()
            self.set_duration_label()
            self.set_logging_date_label()
            self.set_logging_time_label()

            self.currentFilename = row[self.NAME_IDX]
            self.mainWindow.set_title(_("GPX Viewer - %s") % row[self.NAME_IDX])
            return

        self.zoom = 12
        distance = row[self.GPX_IDX].get_moving_data().moving_distance
        maximum_speed = row[self.GPX_IDX].get_moving_data().max_speed
        average_speed = stats.get_average_speed(row[self.GPX_IDX])
        duration = row[self.GPX_IDX].get_moving_data().moving_time
        clat = row[self.GPX_IDX].get_center().latitude
        clon = row[self.GPX_IDX].get_center().longitude
        gpxfrom = row[self.GPX_IDX].get_time_bounds().start_time
        gpxto = row[self.GPX_IDX].get_time_bounds().end_time

        self.set_distance_label(round(distance / 1000, 2))
        self.set_maximum_speed_label(maximum_speed)
        self.set_average_speed_label(average_speed)
        hours, remain = divmod(duration, 3600)
        minutes, seconds = divmod(remain, 60)
        self.set_duration_label(hours, minutes, seconds)
        self.set_logging_date_label('--')
        self.set_logging_time_label('--', '--')
        if gpxfrom:
            self.set_logging_date_label(gpxfrom.strftime("%x"))
            if gpxto:
                self.set_logging_time_label(gpxfrom.strftime("%X"), gpxto.strftime("%X"))

        self.currentFilename = row.get_parent()[self.NAME_IDX]
        self.mainWindow.set_title(_("GPX Viewer - %s") % row[self.GPX_IDX].name)

        if self.autoCenter:
            self.set_centre(clat, clon)

    def load_gpx(self, filename):
        try:
            tracks = parse(open(filename)).tracks
        except GPXException:
            self.show_gpx_error()
            return None

        parent = self.model.append(None, [filename, None, None])
        for i, track in enumerate(tracks):
            color = Gdk.RGBA(*hsv_to_rgb((i / len(tracks) + 1 / 3) % 1.0, 1.0, 1.0))
            self.add_track(parent, track, color)
        if len(self.model) > 1 or len(tracks) > 1:
            self.wTree.get_object("checkmenuitemShowSidebar").set_active(True)
            self.show_track_selector()
        else:
            self.select_trace(next(self.model[0].iterchildren()))
        return track

    def open_gpx(self, *args):
        filechooser = Gtk.FileChooserDialog(title=_("Choose a GPX file to Load"), action=Gtk.FileChooserAction.OPEN,
                                            parent=self.mainWindow)
        filechooser.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.DELETE_EVENT)
        filechooser.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        filechooser.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        filechooser.set_select_multiple(True)
        response = filechooser.run()

        if response == Gtk.ResponseType.OK:
            for filename in filechooser.get_filenames():
                if self.load_gpx(filename):
                    self.recent.add_item("file://" + filename)

        filechooser.destroy()

    def show_gpx_error(self):
        message_box = Gtk.MessageDialog(parent=self.mainWindow, type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
                                        message_format=_("You selected an invalid GPX file. \n Please try again"))
        message_box.run()
        message_box.destroy()
        return None

    def quit(self, w):
        Gtk.main_quit()

    def main(self):
        Gtk.main()

    def open_with_external_app(self, w, app):
        if self.currentFilename:
            os.spawnlp(os.P_NOWAIT, app, app, self.currentFilename)

    def zoom_map_in(self, w):
        self.map.zoom_in()

    def zoom_map_out(self, w):
        self.map.zoom_out()

    def set_centre(self, lat, lon):
        self.map.set_center_and_zoom(lat, lon, self.zoom)

    def set_distance_label(self, distance=None):
        distance = '%.2f' % distance if distance else '--'
        self.wTree.get_object("labelDistance").set_markup(_("<b>Distance:</b> %s km") % distance)

    def set_average_speed_label(self, average_speed=None):
        average_speed = '%.2f' % average_speed if average_speed else '--'
        self.wTree.get_object("labelAverageSpeed").set_markup(_("<b>Average Speed:</b> %s m/s") % average_speed)

    def set_maximum_speed_label(self, maximum_speed=None):
        maximum_speed = '%.2f' % maximum_speed if maximum_speed else '--'
        self.wTree.get_object("labelMaximumSpeed").set_markup(_("<b>Maximum Speed:</b> %s m/s") % maximum_speed)

    def set_duration_label(self, hours="--", minutes="--", seconds="--"):
        self.wTree.get_object("labelDuration").set_markup(
            _("<b>Duration:</b> %(hours)s hours, %(minutes)s minutes, %(seconds)s seconds") % {"hours": hours, "minutes": minutes, "seconds": seconds})

    def set_logging_date_label(self, gpxdate="--"):
        self.wTree.get_object("labelLoggingDate").set_markup(_("<b>Logging Date:</b> %s") % gpxdate)

    def set_logging_time_label(self, gpxfrom="--", gpxto="--"):
        self.wTree.get_object("labelLoggingTime").set_markup(
            _("<b>Logging Time:</b> %(from)s - %(to)s") % {"from": gpxfrom, "to": gpxto})

    def auto_center_toggled(self, item):
        self.autoCenter = item.get_active()

    def button_track_add_clicked(self, *args):
        self.open_gpx()

    def remove_track(self, tracks):
        for t in tracks:
            self.map.track_remove(t)

    def button_track_delete_clicked(self, *args):
        model, _iter = self.tv.get_selection().get_selected()
        if not _iter:
            return
        if self.model.get_value(_iter, self.OSM_IDX):
            self.remove_track(self.model.get_value(_iter, self.OSM_IDX))
        else:
            for child in self.model[_iter].iterchildren():
                self.remove_track(child[self.OSM_IDX])
        self.model.remove(_iter)

    def button_track_properties_clicked(self, *args):
        model, _iter = self.tv.get_selection().get_selected()
        if _iter:
            OsmGpsMapTracks = self.model.get_value(_iter, self.OSM_IDX)
            colorseldlg = Gtk.ColorSelectionDialog("Select track color")
            colorseldlg.get_color_selection().set_current_color(OsmGpsMapTracks[0].props.color.to_color())
            result = colorseldlg.run()
            if result == Gtk.ResponseType.OK:
                color = colorseldlg.get_color_selection().get_current_rgba()
                for OsmGpsMapTrack in OsmGpsMapTracks:
                    OsmGpsMapTrack.set_color(color)
                    self.map.map_redraw()
            colorseldlg.destroy()

    def button_track_inspect_clicked(self, *args):
        pass


class MapZoomSlider(Gtk.HBox):
    def __init__(self, _map):
        Gtk.HBox.__init__(self)

        zo = Gtk.EventBox()
        zo.add(Gtk.Image.new_from_stock(Gtk.STOCK_ZOOM_OUT, Gtk.IconSize.MENU))
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
        hs.set_size_request(100, -1)
        # hs.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        self.pack_start(hs, True, True, 0)

        zi = Gtk.EventBox()
        zi.add(Gtk.Image.new_from_stock(Gtk.STOCK_ZOOM_IN, Gtk.IconSize.MENU))
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
            _map.set_zoom(int(zoom))

    def _on_map_zoom_changed(self, _map, paramspec):
        self.zoom.set_value(_map.props.zoom)
