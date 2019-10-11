from gi.repository import Gtk
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.figure import Figure

class _Chart:

	title = ''
	xlabel = ''
	ylabel = ''

	def chart(self):
		raise NotImplementedError

	def chart_window(self):
		window = Gtk.Window()
		window.add(self.chart())
		window.resize(800,400)
		window.show_all()

	def chart_notebook_page(self):
		return self.chart(),Gtk.Label(self.title)

class ChartNotebook(Gtk.Notebook):
	def __init__(self, *charts):
		Gtk.Notebook.__init__(self)
		for c in charts:
			self.append_page(*c.chart_notebook_page())

class StatBarChart(_Chart):

	show_data_labels = True

	def getBarChartData(self):
		raise NotImplementedError

	def chart(self):
		chart = Figure(tight_layout=True)
		barchart = chart.add_subplot(111)
		barchart.grid(linestyle=':')

		labels, bar_info = self.getBarChartData()
		x = range(len(labels))
		bars = barchart.bar(x, bar_info)
		barchart.set_xlabel(self.xlabel)
		barchart.set_ylabel(self.ylabel)
		barchart.set_xticks(x)
		barchart.set_xticklabels(labels)

		if self.show_data_labels:
			for bar in bars:
				height = bar.get_height()
				barchart.annotate('%0.2f' % height,
					xy=(bar.get_x() + bar.get_width() / 2, height),
					xytext=(0, 3),
					textcoords='offset points',
					ha='center', va='bottom')

		return FigureCanvas(chart)

class LineChart(_Chart):

	def getLineChartData(self):
		raise NotImplementedError

	def chart(self):
		chart = Figure(tight_layout=True)
		graph = chart.add_subplot(111)

		labels, data = self.getLineChartData()
		graph.set_xlabel(self.xlabel)
		graph.set_ylabel(self.ylabel)
		graph.set_xticks(labels)
		graph.plot(data)

		return FigureCanvas(chart)

class WeekStats(StatBarChart):

	title = 'Total Distance Cycled Per Week'
	xlabel = 'week'
	ylabel = 'distance [km]'

	def __init__(self):
		self._weeks = [0]*53

	def addTrace(self, trace):
		week = trace.get_gpxfrom().isocalendar()[1]
		distance = trace.get_distance()
		
		self._weeks[week] += (distance/1000.0)

	def getBarChartData(self):
		wk = 1
		labels = []
		data = []
		for dist in self._weeks:
			if dist:
				data.append(dist)
				labels.append('W%d' % wk)
			wk += 1
		return (labels, data)

class AvgSpeedStats(LineChart):

	title = 'Average Speed'
	xlabel = 'track'
	ylabel = 'avg [m/s]'

	def __init__(self):
		self._avgspeeds = []

	def addTrace(self, trace):
		self._avgspeeds.append(trace.get_average_speed())

	def getLineChartData(self):
		return (range(len(self._avgspeeds)), self._avgspeeds)


