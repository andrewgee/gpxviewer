#
#  gpx.py - Used to hold gpx files for access by other scripts
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

from .gpximport import import_gpx_trace
from math import sqrt, radians, sin, cos, atan2, fabs, pi, acos
from os.path import basename, abspath

def calculate_distance(lat1, lat2, lon1, lon2):
  R = 6371000 #Earth's radius =~ 6371km
  lat1 = radians(lat1)
  lat2 = radians(lat2)
  lon1 = radians(lon1)
  lon2 = radians(lon2)
  
  # Great Circle Distance Formula
  # arc = acos((sin(lat1) * sin(lat2)) + (cos(lat1) * cos(lat2) * cos(lon2 - lon1)))
  # 9.8.2011 Hadmut Danisch hadmut@danisch.de:
  # This formula can fail and abort with a domain exception since the inner part
  # of the expression can become >1.0 in rare cases due to the limited 
  # precision of the floating point arithmetics
  a=(sin(lat1) * sin(lat2)) + (cos(lat1) * cos(lat2) * cos(lon2 - lon1))    
  if a >= 1.0:
    arc=0.0
  elif a <= -1.0:
    arc=math.pi
  else:
    arc=acos(a)
  
  d = R * arc
  return d

class GPXTrace:

  def __init__(self,filename):
    self.trace = import_gpx_trace(filename)
    self._cache = {}

  def _walk_points(self):
    """
    Computes all measurements that require walking over all points
    """
    maxlat = minlat = self.trace['tracks'][0]['segments'][0]['points'][0]['lat']
    maxlon = minlon = self.trace['tracks'][0]['segments'][0]['points'][0]['lon']
    distance = 0
    seconds = 0
    mspeed = 0

    for track in self.trace['tracks']:
      for segment in track['segments']:
        pointp = None
        for point in segment['points']:

          #{max,min}{lat,lon}
          if maxlat < point['lat']:
            maxlat = point['lat']
          elif minlat > point['lat']:
            minlat = point['lat']
          if maxlon < point['lon']:
            maxlon = point['lon']
          elif minlon > point['lon']:
            minlon = point['lon']

          #distance
          if pointp != None:
            #maximum speed
            d = calculate_distance(point['lat'], pointp['lat'], point['lon'], pointp['lon'])
            t = (point['time'] - pointp['time']).microseconds + ((point['time'] - pointp['time']).seconds * 1000000)
            if t > 0:
              s = (d/t)*1000000
              if s > mspeed:
                mspeed = s

            distance += d

          pointp = point

        #segment duration (pointp contains the last point in the segment)
        seconds += (pointp['time'] - segment['points'][0]['time']).seconds

    self._cache["max_lat"] = maxlat
    self._cache["min_lat"] = minlat
    self._cache["max_lon"] = maxlon
    self._cache["min_lon"] = minlon
    self._cache["distance"] = distance
    self._cache["duration"] = seconds
    self._cache["max_speed"] = mspeed

  def _get_cached_value(self, name):
    if name not in self._cache:
      self._walk_points()
    return self._cache[name]
        
  def get_points(self):
    tracks = []
    
    for track in self.trace['tracks']:
      segments = []
      for segment in track['segments']:
        points = []
        for point in segment['points']:
          points.append((radians(point['lat']),radians(point['lon'])))
        
        segments.append(points)
        
      tracks.append(segments)
    
    return tracks

  def get_display_name(self):
    try:
      return self.trace["metadata"]["name"]
    except KeyError:
      return self.get_filename()
  
  def get_filename(self):
    return basename(self.trace['filename'])

  def get_full_path(self):
    return abspath(self.trace['filename'])

  def get_max_lat(self):
    return self._get_cached_value("max_lat")

  def get_min_lat(self):
    return self._get_cached_value("min_lat")

  def get_max_lon(self):
    return self._get_cached_value("max_lon")

  def get_min_lon(self):
    return self._get_cached_value("min_lon")

  def get_centre(self):
    maxlat = self.get_max_lat()
    minlat = self.get_min_lat()
    maxlon = self.get_max_lon()
    minlon = self.get_min_lon()
    return (maxlat+minlat)/2,(maxlon+minlon)/2
    
  def get_average_speed(self):
    #return self._get_cached_value("distance")/self._get_cached_value("duration")
    # 9.8.2011 Hadmut Danisch hadmut@danisch.de:
    # duration can become 0 in special cases and thus cause division by zero
    dis = self._get_cached_value("distance")
    dur = self._get_cached_value("duration")
    if dur == 0:
      return 0
    return dis/dur
  
  def get_distance(self):
    return self._get_cached_value("distance")
    
  def get_duration(self):
    return self._get_cached_value("duration")
    
  def get_gpxfrom(self):
    return self.trace['tracks'][0]['segments'][0]['points'][0]['time']

  def get_gpxto(self):
    return self.trace['tracks'][-1]['segments'][-1]['points'][-1]['time']
  
  def get_maximum_speed(self):
    return self._get_cached_value("max_speed")

