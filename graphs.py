import matplotlib.pyplot as plt
import matplotlib.dates as mdt
import mpld3
import base64
from io import BytesIO
from datetime import datetime
from datetime import timedelta
#from enum import Enum

#class Interval(enum.Enum):
	#HRS = "HRS"
	#WEEK = "WEEK"
	#MONTH = "MONTH"
	#ALL = "ALL"

def saturation_graph(interval="ALL"):	
	#TODO: Find more elegant way to do this
	earliest_date = datetime(1970, 1, 1)
	if interval == "HRS":
		earliest_date = datetime.now() - timedelta(hours=48)
	elif interval == "WEEK":
		earliest_date = datetime.now() - timedelta(weeks=1)
	elif interval == "MONTH":
		earliest_date = datetime.now() - timedelta(days=30)
		
	x, y = [], []
	f = open("data.csv", "r")
	f.readline() #ignore header line
	
	for row in list(f):
		row = row.strip().split(',')
		if (datetime.strptime(row[0], '%d/%m/%Y %H:%M') >= earliest_date):
			x.append(datetime.strptime(row[0], '%d/%m/%Y %H:%M'))
			y.append(float(row[1]))
			
	f.close()
	
	fig = plt.plot(x, y, color="#00b6d6")
	plt.gcf().autofmt_xdate()
	plt.gca().xaxis.set_major_formatter(mdt.DateFormatter('%d %b %H:%M'))
	plt.xticks(rotation=45)
	plt.ylabel("Saturation %")
	plt.title("Saturation level over time")
	plt.grid(b=True, which='major', color='#DDDDDD', linestyle='-')
	plt.draw()
	plt.savefig('satgraph.svg')
	plt.clf()
