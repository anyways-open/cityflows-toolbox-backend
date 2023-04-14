from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

import json
import hashlib 
import traceback
from collections import defaultdict
import pandas as pd
from sklearn.cluster import DBSCAN
import numpy as np
from datetime import timedelta

class Modality (models.Model):
    name = models.CharField (max_length = 10, db_index = True)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Modalities"

class SensorType (models.Model):
    name = models.CharField (max_length = 30, db_index = True)

    def __str__(self):
        return self.name
    def card (self):
        return {'name': self.name}

class Sensor (models.Model):
    ref = models.CharField (max_length = 40, db_index = True)
    location = models.TextField ()
    availableModalities = models.ManyToManyField ('Modality')
    hasReverse = models.BooleanField ()
    meta = models.TextField (blank=True, null=True)
    sensorType = models.ForeignKey ('SensorType', db_index = True, related_name = 'sensors', on_delete = models.CASCADE)

    def addressString (self):
        try:
            meta = json.loads (self.meta)
            if 'addressString' in meta:
                return meta['addressString']
        except:
            pass
        return ''

    # returns the dictionary representation of relevant information to use in the API requests
    def card (self):
        extraFields = {}
        try:
            meta = json.loads (self.meta)
            for k in ['addressString']:
                if k in meta:
                    extraFields[k] = meta[k]
        except:
            print (traceback.format_exc())
        return {
            "ref": self.ref,
            "location": self.getLocationDic (),
            "modalities": sorted([mod.name for mod in self.availableModalities.all()]),
            "hasReverse": self.hasReverse,
            "sensorType": self.sensorType.card(),
            "extraFields": extraFields
        }
    # reformat of the location information depending on type
    def getLocationDic (self):
        try:
            loc = json.loads (self.location)
            if loc["type"] == 'point':
                return loc
            if loc["type"] == 'geojson':
                res = json.loads (loc['coords'])['features'][0]
                return res
            if loc["type"] == 'linestring':
                locString = loc['coords']
                locString = locString.split ('(')[1]
                locString = locString.split (')')[0]
                return {
                    'id': self.ref,
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[float(coord) for coord in coordPair.strip().split (' ')] for coordPair in locString.split (',')]
                    },  
                    "properties": {"radius": 1}
                }
            return loc
        except:
            print (traceback.format_exc())
        return {}

class SensorTrack (models.Model):
    sensor = models.ForeignKey ('Sensor', db_index = True, related_name = 'tracks', on_delete = models.CASCADE)
    isReverseChannel = models.BooleanField (db_index = True, default = False)
    modality = models.ForeignKey ('Modality', db_index = True, related_name = 'sensorTracks', on_delete = models.CASCADE)

    def __str__(self):
        return self.sensor.ref + ' ' + self.modality.name + ' ' + ('rev' if self.isReverseChannel else '')

    def nameForGraph (self, timePeriodCounter, withSensorRef):
        return ((self.sensor.ref + " " + self.sensor.addressString () + " ") if withSensorRef else "") + self.modality.name + (" reverse" if self.isReverseChannel else "") + (("( time window " + str (timePeriodCounter + 1) + ")") if timePeriodCounter >= 0 else "")

    def availableDatesSpan (self):
        allDates = [v['date'] for v in self.dMeasurements.order_by ('date').values('date')]
        if len (allDates) > 0:
            return (allDates[0], allDates[-1])
        else:
            return None

    def exploreDataConsistency (self):
        allCounts = [val for val in self.hMeasurements.values ('date', 'hour', 'count')]
        adf = pd.DataFrame.from_records (allCounts)
        #(re-) parsing the date field in case it is not yet in datetime format
        adf['date'] = pd.to_datetime(adf['date'])
        #creating a new dataframe with per day aggregation and renaming the columns for a flat index
        adfd = adf.groupby(['date'], as_index=False).agg({'count':['count','sum']})
        adfd.columns = ["_".join(col_name).rstrip('_') for col_name in adfd.columns]
        adfd = adfd.rename (columns={'count_count':'count'})
        #we will exploit the date as an index
        adfd.set_index ('date', inplace=True)
        #checking global min threshold - the signal is seen in at least 3 separate hours...
        adfd['MinThresholdPassed'] = adfd['count'] > 2
        #performing the DBSCAN clustering and finding the outliers
        if len(adfd) > 0:
            clustering = DBSCAN(eps=0.5, min_samples=4).fit_predict(np.array (adfd['count']).reshape (-1,1))
            adfd['DBSCANPassed'] = clustering != -1
        else:
            adfd['DBSCANPassed'] = False
        #computing the rolling averages and comparing with the fixed quantiles in the dataset (having a discount on the lower end)
        adfd['rolling'] = adfd['count'].rolling ('5D', center=True, min_periods=1).mean ()
        adfd['rolling3MQ50D85'] = 0.85 * adfd['count'].rolling ('30D', center=True, min_periods=10).median ()
        adfd['rolling3MQ75'] = adfd['count'].rolling ('30D', center=True, min_periods=10).quantile (0.75)
        adfd['residual'] = adfd['count'] - adfd['rolling']
        adfd['PerformanceThresholdPassed'] = (adfd['rolling'] > adfd['rolling3MQ50D85']) | (adfd['count'] >= adfd['rolling3MQ75'])
        datesSpan = self.availableDatesSpan ()
        #performanceThreshold test is not relevant when 15 days or less, so forcing the "passed" state
        if datesSpan and (datesSpan[1] - datesSpan[0] < timedelta (days=16)):
            adfd['PerformanceThresholdPassed'] = True        
        #shortcut for the combination of all tests
        adfd['AllTestsPassed'] = adfd['MinThresholdPassed'] & adfd['DBSCANPassed'] & adfd['PerformanceThresholdPassed']
        tests = ['AllTests', 'PerformanceThreshold', 'MinThreshold', 'DBSCAN']
        #verifying that the test types are present in the DB
        for name in tests:
            if not QualityValidationTest.objects.filter (name__iexact = name).first():
                QualityValidationTest.objects.create (name = name)
        testNameToObject = {name:QualityValidationTest.objects.filter (name__iexact = name).first() for name in tests}
        #cleaning previous results and daily totals (if any) --- in case of updates
        self.dMeasurements.all().delete ()
        self.qualityValidationResults.all().delete()
        #saving the outcomes
        for rowDate,row in adfd.iterrows ():
            DMeasurement.objects.create (sensor=self, date=rowDate.date(), count=row['count'], count_sum=row['count_sum'])
            for testName in tests:
                QualityValidationResult.objects.create (sensor=self, date=rowDate.date(), test=testNameToObject[testName], passed=row[testName + 'Passed'])

class HMeasurement (models.Model):
    sensor = models.ForeignKey ('SensorTrack', db_index = True, related_name = 'hMeasurements', on_delete = models.CASCADE)
    date = models.DateField (db_index = True)
    hour = models.IntegerField (db_index = True)
    count = models.FloatField () #measurement value

class DMeasurement (models.Model):
    sensor = models.ForeignKey ('SensorTrack', db_index = True, related_name = 'dMeasurements', on_delete = models.CASCADE)
    date = models.DateField (db_index = True)
    count = models.IntegerField () #number of measurements
    count_sum = models.FloatField () #cumulative count

class QualityValidationTest (models.Model):
    name = models.CharField (max_length = 30, db_index = True)

    def __str__(self):
        return self.name

class QualityValidationResult (models.Model):
    sensor = models.ForeignKey ('SensorTrack', db_index = True, related_name = 'qualityValidationResults', on_delete = models.CASCADE)
    date = models.DateField (db_index = True)
    test = models.ForeignKey ('QualityValidationTest', db_index = True, related_name = 'qualityValidationResults', on_delete = models.CASCADE)
    passed = models.BooleanField (db_index = True)
