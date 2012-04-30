# -*- coding: utf-8 -*-
#  kate: space-indent on; indent-width 2; mixedindent off; indent-mode python;

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

from datetime import *
from math import sqrt, radians, sin, cos, atan2, fabs, pi, acos
from os.path import basename, abspath

# For parser
import xml.dom.minidom as minidom
from utils.iso8601 import parse_date as parse_xml_date

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

class GPXPoint:
  ''' A GPX point. It might be part of the track or standalone (waypoint) '''
  
  def __init__(self, tsnode, parent):
    ''' Init from a GPX XML node element '''
    self.parent = parent
    
    # Init props
    self.lat = None
    self.lon = None
    self.ele = None
    self.description = None
    self.time = None
    self.name = None
    
    if tsnode.attributes["lat"] != "" and tsnode.attributes["lon"] != "":
        self.lat = float(tsnode.attributes["lat"].value)
        self.lon = float(tsnode.attributes["lon"].value)
    
    for tpnode in tsnode.childNodes:
        if tpnode.nodeName == "ele":
            self.ele = float(tpnode.childNodes[0].nodeValue)
        elif tpnode.nodeName == "desc":
            self.description = tpnode.childNodes[0].nodeValue
        elif tpnode.nodeName == "time":
            self.time = parse_xml_date(tpnode.childNodes[0].nodeValue)
        elif tpnode.nodeName == "name":
            self.name = tpnode.childNodes[0].nodeValue
    
  def getRadLat(self):
    ''' Returns lat in radians '''
    return radians(self.lat)
  
  def getRadLon(self):
    ''' Returns lng in radians '''
    return radians(self.lon)

class GPXTrackSegment:
  ''' A track segment (collection of points) '''

  def __init__(self, tnode, parent):
    ''' Init from GPX XML node '''
    self.parent = parent
    self._iterindex = -1
    self._points = []
    for tsnode in tnode.childNodes:
        if tsnode.nodeName == "trkpt":
            self._points.append(GPXPoint(tsnode, self))

  def getPoints(self):
    return self._points

  def __len__(self):
    return len(self._points)
  def __getitem__(self, num):
    return self._points[num]
  def __iter__(self):
    self._iterindex = -1
    return self
  def next(self):
    self._iterindex += 1
    if self._iterindex >= len(self):
      raise StopIteration
    return self[self._iterindex]

class GPXTrack:
  ''' A track (collection of segments) '''
  
  def __init__(self, node, parent):
    ''' Creates a new GPXTrack from a GPX XML node '''
    self.parent = parent
    self._iterindex = -1
    self._segments = []
    
    for tnode in node.childNodes:
      if tnode.nodeName == "trkseg":
        seg = GPXTrackSegment(tnode, self)
        if len(seg) > 0:
          self._segments.append(seg)

  def getSegments(self):
    return self._segments

  def __len__(self):
    return len(self._segments)
  def __getitem__(self, num):
    return self._segments[num]
  def __iter__(self):
    self._iterindex = -1
    return self
  def next(self):
    self._iterindex += 1
    if self._iterindex >= len(self):
      raise StopIteration
    return self[self._iterindex]

class GPXFile:
  ''' A GPX file is a container of GPXTraces, GPXWaypoints, and metadata'''

  def __init__(self, filename):
    ''' Parses GPX XML and inits a GPXFile object '''
    
    # Init vars
    self._cache = {}
    self._waypoints = []
    self._tracks = []
    
    # Init metadata
    self.filename = filename
    self.name = None
    self.description = None
    self.time = None
    self.author = None
    self.copyright = None
    self.link = None
    self.keyworks = None
    
    doc = minidom.parse(filename)
    doce = doc.documentElement

    if doce.nodeName != "gpx":
      raise Exception
    
    e = doce.childNodes
    for node in e:
      if node.nodeName == "metadata":
        self._parseMetadata(node)
      elif node.nodeName == "trk":
        self._tracks.append(GPXTrack(node, self))
      elif node.nodeName == "wpt":
        self._waypoints.append(GPXPoint(node, self))

  def _walkPoints(self):
    """
    Computes all measurements that require walking over all points
    """
    maxlat = minlat = self._tracks[0][0][0].lat
    maxlon = minlon = self._tracks[0][0][0].lon
    distance = 0
    seconds = 0
    mspeed = 0

    for track in self._tracks:
      for segment in track.getSegments():
        pointp = None
        for point in segment.getPoints():

          #{max,min}{lat,lon}
          if maxlat < point.lat:
            maxlat = point.lat
          elif minlat > point.lat:
            minlat = point.lat
          if maxlon < point.lon:
            maxlon = point.lon
          elif minlon > point.lon:
            minlon = point.lon

          #distance
          if pointp != None:
            #maximum speed
            d = calculate_distance(point.lat, pointp.lat, point.lon, pointp.lon)
            t = (point.time - pointp.time).microseconds + ((point.time - pointp.time).seconds * 1000000)
            if t > 0:
              s = (d/t)*1000000
              if s > mspeed:
                mspeed = s

            distance += d

          pointp = point

        #segment duration (pointp contains the last point in the segment)
        seconds += (pointp.time - segment[0].time).seconds

    self._cache["max_lat"] = maxlat
    self._cache["min_lat"] = minlat
    self._cache["max_lon"] = maxlon
    self._cache["min_lon"] = minlon
    self._cache["distance"] = distance
    self._cache["duration"] = seconds
    self._cache["max_speed"] = mspeed

  def _getCachedValue(self, name):
    if name not in self._cache:
      self._walkPoints()
    return self._cache[name]
        
  def getTracks(self):
    return self._tracks

  def getWaypoints(self):
    return self._waypoints

  def getDisplayName(self):
    if self.name:
      return self.name
    else:
      return self.filename
  
  def getFilename(self):
    return basename(self.filename)

  def getFullPath(self):
    return abspath(self.filename)

  def getMaxLat(self):
    return self._getCachedValue("max_lat")

  def getMinLat(self):
    return self._getCachedValue("min_lat")

  def getMaxLon(self):
    return self._getCachedValue("max_lon")

  def getMinLon(self):
    return self._getCachedValue("min_lon")

  def getCentre(self):
    maxlat = self.getMaxLat()
    minlat = self.getMinLat()
    maxlon = self.getMaxLon()
    minlon = self.getMinLon()
    return (maxlat+minlat)/2,(maxlon+minlon)/2
    
  def getAverageSpeed(self):
    #return self._get_cached_value("distance")/self._get_cached_value("duration")
    # 9.8.2011 Hadmut Danisch hadmut@danisch.de:
    # duration can become 0 in special cases and thus cause division by zero
    dis = self._getCachedValue("distance")
    dur = self._getCachedValue("duration")
    if dur == 0:
      return 0
    return dis/dur
  
  def getDistance(self):
    return self._getCachedValue("distance")
    
  def getDuration(self):
    return self._getCachedValue("duration")
    
  def getGpxFrom(self):
    return self._tracks[0][0][0].time

  def getGpxTo(self):
    return self._tracks[-1][-1][-1].time
  
  def getMaximumSpeed(self):
    return self._getCachedValue("max_speed")

  def _parseMetadata(self, node):
    ''' Parses metadata from an XML node ans stores it to object '''
    for mnode in node.childNodes:
      if mnode.nodeName == "name":
        self.name = mnode.childNodes[0].nodeValue
          
      elif mnode.nodeName == "desc":
        try:
          self.description = mnode.childNodes[0].nodeValue
        except Exception as e:
          print 'WARNING: Exception parsing metadata description:', e
          
      elif mnode.nodeName == "author":
        self.author = {}
        for anode in mnode.childNodes:
          if anode.nodeName == "name":
            if len(anode.childNodes):
              self.author['name'] = anode.childNodes[0].nodeValue
            else:
              self.author['name'] = anode.nodeValue
          elif anode.nodeName == "email":
            if len(anode.childNodes):
              self.author['email'] = anode.childNodes[0].nodeValue
            elif anode.hasAttributes():
              try:
                anode.attributes['id']
                anode.attributes['domain']
              except KeyError:
                self.author['email'] = anode.nodeValue
              else:
                self.author['email'] = anode.attributes['id'].value + '@' + anode.attributes['domain'].value
            else:
              self.author['email'] = anode.nodeValue
          elif anode.nodeName == "link":
            self.author['link'] = anode.childNodes[0].nodeValue
                  
      elif mnode.nodeName == "copyright":
        self.copyright = {}
        if mnode.attributes["author"].value != "":
          self.copyright['author'] = mnode.attributes["author"].value
        for cnode in mnode.childNodes:
          if cnode.nodeName == "year":
            self.copyright['year'] = cnode.childNodes[0].nodeValue
          elif cnode.nodeName == "license":
            self.copyright['license'] = cnode.childNodes[0].nodeValue
                  
      elif mnode.nodeName == "link":
        self.link = {}
        if mnode.attributes["href"].value != "":
          self.link['href'] = mnode.attributes["href"].value
        for lnode in mnode.childNodes:
          if lnode.nodeName == "text":
            self.link['text'] = lnode.childNodes[0].nodeValue
          elif lnode.nodeName == "type":
            self.link['type'] = lnode.childNodes[0].nodeValue
                  
      elif mnode.nodeName == "time":
        self.time = parse_xml_date(mnode.childNodes[0].nodeValue)
                  
      elif mnode.nodeName == "keywords":
        self.keywords = mnode.childNodes[0].nodeValue
