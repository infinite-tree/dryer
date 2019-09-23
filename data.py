import datetime
import json
import os
import time

from influxdb import InfluxDBClient

INFLUXDB_CONFIG_FILE = os.path.expanduser("~/.influxdb.config")



class DataSource(object):
    def __init__(self, log):
        self.Log = log
        self.Log.info("Reading InfluxDB config from %s"%(INFLUXDB_CONFIG_FILE))
        with open(INFLUXDB_CONFIG_FILE) as f:
            config = json.load(f)

        self.Influx = InfluxDBClient(config['host'],
                                     config['port'],
                                     config['login'],
                                     config['password'],
                                     config['database'],
                                     ssl=True,
                                     timeout=60)
        self.Points = []
        self.LastSent = datetime.datetime.now()
        self.Interval = 60
        self.MaxPoints = 250

    def getTime(self):
        now = datetime.datetime.utcnow()
        return now.strftime('%Y-%m-%dT%H:%M:%SZ')

    def queryCurrentTemps(self):
        r = self.query('''SELECT "sensor","value" FROM "temperature_fahrenheit" WHERE ("location" = 'dryer') AND time >= now() - 5m GROUP BY "sensor" ORDER by time DESC''')
        points = [p for p in r]
        result = {}
        self.Log.debug("Temperature data: %s"%points)
        for sensor_data in points:
            if len(sensor_data) > 0:
                result[sensor_data[0]['sensor']] = int(sensor_data[0]['value'])
        # self.Log.debug("temp result: %s"%result)
        return result

    def queryCurrentHumidty(self):
        r = self.query('''SELECT "sensor","value" FROM "humidity_percentage" WHERE ("location" = 'dryer') AND time >= now() - 5m GROUP BY "sensor" ORDER by time DESC''')
        points = [p for p in r]
        self.Log.debug("Humidity data: %s"%points)
        result = {}
        for sensor_data in points:
            if len(sensor_data) > 0:
                result[sensor_data[0]['sensor']] = int(sensor_data[0]['value'])
        # self.Log.debug("humidity result: %s"%result)
        return result

    def writePoints(self):
        ret = None

        # drop old points if there are too many
        if len(self.Points) > self.MaxPoints:
            self.Points = self.Points[self.MaxPoints:]

        for x in range(10):
            try:
                ret = self.Influx.write_points(self.Points)
            except Exception as e:
                self.Log.error("Influxdb point failure: %s"%(e))
                ret = 0
            if ret:
                self.Log.info("%s - Sent %d points to Influx"%(datetime.datetime.now(), len(self.Points)))
                self.LastSent = datetime.datetime.now()
                self.Points = []
                return ret

            time.sleep(0.2)

        self.Log.error("%s - Failed to send %d points to Influx: %s"%(datetime.datetime.now(), len(self.Points), ret))
        return ret

    # def sendMeasurement(self, measurement, sensor, value):
    #     # FIXME: update for dryer
    #     point = {
    #         "measurement": measurement,
    #         "tags": {
    #             "location": self.Location,
    #             "sensor": self.Controller,
    #             "outlet": outlet
    #         },
    #         "time": self.getTime(),
    #         "fields": {
    #             "value": value
    #         }
    #     }

    #     self.Points.append(point)

    #     now = datetime.datetime.now()
    #     if len(self.Points) >= self.MaxPoints or (now - self.LastSent).seconds >= self.Interval:
    #         return self.writePoints()
    #     return True

    def query(self, *args, **kwargs):
        for x in range(3):
            try:
                return self.Influx.query(*args, **kwargs)
            except Exception as e:
                self.Log.error("Query failed: %s"%str(e))

            time.sleep(0.2)


