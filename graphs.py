import matplotlib.pyplot as plt
import matplotlib.dates as mdt
import mpld3
import base64
from io import BytesIO
from datetime import datetime

def saturation_graph():
	x, y = [], []
	f = open("data.csv", "r")
	f.readline() #ignore header line
	for row in list(f):
		row = row.strip().split(',')
		x.append(datetime.strptime(row[0], '%d/%m/%Y %H:%M'))
		y.append(float(row[1]))
	
	fig = plt.plot(x, y, color="#00b6d6")
	plt.gcf().autofmt_xdate()
	plt.gca().xaxis.set_major_formatter(mdt.DateFormatter('%d %b %H:%M'))
	plt.xticks(rotation=45)
	plt.ylabel("Saturation %")
	plt.title("Saturation level over time")
	plt.grid(b=True, which='major', color='#DDDDDD', linestyle='-')
	plt.draw()
	plt.savefig('satgraph.svg')
