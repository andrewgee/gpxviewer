import gtk
import pygtk_chart.bar_chart
import pygtk_chart.line_chart as line_chart

class _Chart:

	title = ""

	def chart(self):
		raise NotImplementedError

	def chart_window(self):
		window = gtk.Window()
		window.add(self.chart())
		window.resize(800,400)
		window.show_all()

	def chart_notebook_page(self):
		return self.chart(),gtk.Label(self.title)

class ChartNotebook(gtk.Notebook):
	def __init__(self, *charts):
		gtk.Notebook.__init__(self)
		for c in charts:
			self.append_page(*c.chart_notebook_page())

class StatBarChart(_Chart):

	show_data_labels = True

	def getBarChartData(self):
		raise NotImplementedError

	def chart(self):
		barchart = pygtk_chart.bar_chart.BarChart()
		barchart.title.set_text(self.title)
		barchart.grid.set_visible(True)
		barchart.grid.set_line_style(pygtk_chart.LINE_STYLE_DOTTED)
		barchart.set_draw_labels(self.show_data_labels)

		for bar_info in self.getBarChartData():
			bar = pygtk_chart.bar_chart.Bar(*bar_info)
			barchart.add_bar(bar)

		return barchart

class LineChart(_Chart):

	def getLineChartData(self):
		raise NotImplementedError

	def chart(self):
		chart = line_chart.LineChart()
		chart.title.set_text(self.title)

		data = self.getLineChartData()
		graph = line_chart.Graph("avg", "avg", data)
		graph.set_type(line_chart.GRAPH_LINES)
		chart.add_graph(graph)

		return chart

class WeekStats(StatBarChart):

	title = 'Total Distance Cycled Per Week'

	def __init__(self):
		self._weeks = [0]*53

	def addTrace(self, trace):
		week = trace.get_gpxfrom().isocalendar()[1]
		distance = trace.get_distance()
		
		self._weeks[week] += (distance/1000.0)

	def getBarChartData(self):
		wk = 1
		data = []
		for dist in self._weeks:
			if dist:
				data.append( (str(wk),float(int(dist)),"W%d"%wk) )
			wk += 1
		return data

class AvgSpeedStats(LineChart):

	title = "Average Speed"

	def __init__(self):
		self._i = 0
		self._avgspeeds = []

	def addTrace(self, trace):
		self._avgspeeds.append( (self._i, trace.get_average_speed()) )
		self._i += 1

	def getLineChartData(self):
		return self._avgspeeds


