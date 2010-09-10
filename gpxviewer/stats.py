import gtk
import pygtk_chart.bar_chart

class StatBarChart:

	def getBarChartData(self):
		raise NotImplementedError

	def chart(self):
		barchart = pygtk_chart.bar_chart.BarChart()
		barchart.title.set_text('Total Distance Cycled Per Week')
		barchart.grid.set_visible(True)
		barchart.grid.set_line_style(pygtk_chart.LINE_STYLE_DOTTED)

		for bar_info in self.getBarChartData():
			bar = pygtk_chart.bar_chart.Bar(*bar_info)
			barchart.add_bar(bar)

		window = gtk.Window()
		window.add(barchart)
		window.resize(800,400)
		window.show_all()

class WeekStats(StatBarChart):
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

