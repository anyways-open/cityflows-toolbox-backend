from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.utils.timezone import make_aware
from oauth2_provider.decorators import protected_resource

import os
import pickle
import json
import traceback
import os
import holidays
import csv
import numpy as np
import pandas as pd

from dateutil.parser import parse, isoparse
from datetime import datetime, time, timedelta
from random import randint 
from collections import defaultdict
from scipy.stats import kstest
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.statespace.sarimax import SARIMAX

import app.models
from app.translations import getTranslatedString
from app.tools import jsonResponseFromDic, getDecodedRequestBody, formatFloat

# TODO: avoid the hardcoded year
BE_HOLIDAYS = [holiday[0] for holiday in holidays.Belgium (years=[2021]).items()]

# p-value threshold for Kolmogorov-Smirnov tests
pThreshold = 0.05

# explicit view at index path; as the robots are continuously pinging sites, this avoids showing the sitemap in debug mode
def index (request):
    return HttpResponseForbidden ()
    
# general API endpoint; has the try-catch global error check for debug reasons, follows the request further
@protected_resource()
@csrf_exempt
def genericAPIRequest (request):
    try:
        ajaxRequest = json.loads(getDecodedRequestBody(request))
        endpoint = ajaxRequest['endpoint']
        res = serveAPIRequest (ajaxRequest, endpoint)
        if type (res) == dict:
            return jsonResponseFromDic (res)
        else:
            return res
    except: 
        print (traceback.format_exc())
        return jsonResponseFromDic ({'status':'error_occurred'})

# verification that the endpoint requested via the API is valid and its treatment
def serveAPIRequest (ajaxRequest, endpoint):
    if endpoint in ['getSensorsCollection', 'getSensorCard', 'getSensorCards', 'getMultiSourceTrack']:
        return globals()[endpoint] (ajaxRequest)
    return {'status':'error_occurred', 'error': 'incorrect endpoint'}

# return all the available sensors via API
def getSensorsCollection (request):
    res = []
    allTestsTest = app.models.QualityValidationTest.objects.filter (name='AllTests').first()
    if not allTestsTest:
        return HttpResponse (json.dumps({"status":"ok", "sensorCards": []}))
    for sensor in app.models.Sensor.objects.all ():
        card = sensor.card()
        trackQualities = []
        for track in sensor.tracks.all ():
            datesSpan = track.availableDatesSpan()
            if datesSpan:
                trackQualities.append (track.qualityValidationResults.filter (test=allTestsTest).filter (passed=True).count() / ((datesSpan[1] - datesSpan[0]).days + 1))
        if len (trackQualities) > 0:
            card['quality'] = 100 * np.mean (trackQualities)
            res.append (card)
	
    return HttpResponse (json.dumps({"status":"ok", "sensorCards": res}))

# return a particular sensor (with specified ref; if any) via API
def getSensorCard (ajaxRequest):
    ref = ajaxRequest['ref']
    cS = app.models.Sensor.objects.filter (ref=ref).first ()
    if not cS:
        print ('no sensor' + ref)
        return {'status': 'error_occurred', 'error': 'No sensor found'}
    return {'status': 'ok', 'sensor': cS.card()}

# return particulars sensor (with ref in "refs" param; if any) via API
def getSensorCards (ajaxRequest):
    refs = ajaxRequest['refs']
    if not refs:
        return {'status': 'ok', 'sensors': []}
    cards = []
    for ref in refs.split (','):
        cS = app.models.Sensor.objects.filter (ref=ref.strip()).first ()
        if not cS:
            print ('no sensor' + ref)
            continue
        cards.append (cS.card())
    return {'status': 'ok', 'sensors': cards}

# created a DataFrame from the collection of daily measurements
# if there are gaps in data, they are filled with the previous observed count (the last available day)
# isReal column keeps track if it is a real observed value or a filled in
# no weekly pattern is imposed, just filling the blanks
# the gap filling is done to further use in weekly patterns detection for example
def convertMeasurementsToDF (dMeasurements): 
    dateToVal = {d['date'].strftime ("%Y-%m-%d"):d['count_sum'] for d in dMeasurements}
    data = []
    for date in pd.date_range (min(dateToVal.keys()), max(dateToVal.keys())):
        dateString = date.strftime ("%Y-%m-%d")
        if dateString in dateToVal:
            data.append ([date, dateToVal[dateString], True])
        else:
            data.append ([date, None, False])
    df = pd.DataFrame (data, columns=["date", "countSum", "isReal"])
    df.set_index ('date', inplace=True)
    df.fillna(method="ffill", inplace=True)
    return df

# decomposition in trend/weekly/residual components
def getTrueSeasonalDecompose (dMeasurements):
    df = convertMeasurementsToDF (dMeasurements)
    decomp = seasonal_decompose(df['countSum'], model='additive', period=7, extrapolate_trend='freq')
    df = df.merge (decomp.trend.rename ("trend"), left_index=True, right_index=True)
    df = df.merge (decomp.seasonal.rename ("seasonal"), left_index=True, right_index=True)
    df = df.merge (decomp.resid.rename ("resid"), left_index=True, right_index=True)
    return df[df.isReal == True].reset_index(), df

# parse datetime from and to objects from timePeriods coming from the API request
def getFromToFromTimePeriod (timePeriod):
    try:
        tpFrom = parse (str(timePeriod['from'])) if isinstance(timePeriod['from'], str) else  datetime.fromtimestamp (timePeriod['from']/ 1000)
    except:
        tpFrom = None
    try:
        tpTo = parse (str(timePeriod['to'])) if isinstance(timePeriod['to'], str) else  datetime.fromtimestamp (timePeriod['to']/ 1000)
    except:
        tpTo = None
    return tpFrom, tpTo

# filter only the measurements following the configuration of the timePeriod (dates / day types / holidays / tests passed)
def filterMeasurementsForTimePeriod (measurements, timePeriod, sensorTrack):
    tpFrom, tpTo = getFromToFromTimePeriod (timePeriod)
    res = measurements.filter (date__gte = tpFrom).filter (date__lte = tpTo)
    for dayCounter, day in enumerate(['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']):
        if not timePeriod[day]:
            res = res.exclude (date__week_day = dayCounter + 1)
    if not timePeriod['Holiday']:
        res = res.exclude (date__in = BE_HOLIDAYS)
    if not timePeriod['Non-holiday']:
        res = res.filter (date__in = BE_HOLIDAYS)
    for testName in ['PerformanceThreshold', 'MinThreshold', 'DBSCAN']:
        if not timePeriod[testName]:
            cTest = app.models.QualityValidationTest.objects.filter (name__iexact = testName).first()
            if cTest:
                failedDates = [qvr['date'] for qvr in sensorTrack.qualityValidationResults.filter (passed=False).filter (date__gte = tpFrom).filter (date__lte = tpTo).filter (test=cTest).values ('date') ]
                res = res.exclude (date__in = failedDates)
    return res.order_by('date')

# main routine for the analysis page
# parses the sensors configuration and then uses either extractRawCSVData or fillSensorTracks to continue
def getMultiSourceTrack (ajaxRequest):
    lang = ajaxRequest['lang'] if 'lang' in ajaxRequest else 'en'
    refModalityReverseCombinations = ajaxRequest['refModalityReverseCombinations']
    cTs = []
    for ref in refModalityReverseCombinations:
        for modality in refModalityReverseCombinations[ref]:
            for isReverseString in refModalityReverseCombinations[ref][modality]:
                if not refModalityReverseCombinations[ref][modality][isReverseString]:
                    continue
                isReverse = isReverseString == 'true'
                cS = app.models.Sensor.objects.filter (ref=ref).first ()
                if not cS:
                    print ('no sensor' + ref)
                    continue
                    
                if modality != 'All':
                    cT = cS.tracks.filter (modality__name = modality).filter (isReverseChannel = isReverse).first ()
                    if not cT:
                        return {'status': 'error_occurred', 'error': 'Incorrect sensor-modality-reverse combination'}
                    cTs.append (cT)
                else:
                    cTs += list(cS.tracks.all())
    timePeriods = ajaxRequest['timePeriods']
    viewType = ajaxRequest['viewType']
    basePopulationSensorRef = ajaxRequest['basePopulationSensorRef'] if 'basePopulationSensorRef' in ajaxRequest else None
    if basePopulationSensorRef not in refModalityReverseCombinations:
        basePopulationSensorRef = None
    if viewType == 'extractRawCSVData':
        return extractRawCSVData (cTs, timePeriods)
    if len (cTs) == 0:
        return {'status': 'ok', 'multiSourceTracks': { "contents": [{
                "type": 'text',
                "title": getTranslatedString ('No sensor tracks selected', lang),
                "subtitle":  getTranslatedString ('Please select the desired modalities for each sensor in the left menu', lang),
                "isError": True
        }] }}
    if len (timePeriods) == 0:
        return {'status': 'ok', 'multiSourceTracks': { "contents": [{
                "type": 'text',
                "title": getTranslatedString ('No time windows configured', lang),
                "subtitle":  getTranslatedString ('Please create and configure at least one time window in the left menu', lang),
                "isError": True
        }] }}
    return {'status': 'ok', 'multiSourceTracks': { "contents":fillSensorTracks (cTs, timePeriods, viewType, True, basePopulationSensorRef, lang) }}

# creation of the in-memory CSV export file based on selected sensorTracks (cTs) and timePeriods
def extractRawCSVData (cTs, timePeriods):
    response = HttpResponse(content_type='text/plain')  
    response['Content-Disposition'] = 'attachment; filename="export.csv"'
    writer = csv.writer(response)
    writer.writerow(["sensor_ref", "modality", "is_reverse_channel", "time_period_counter", "date", "hour", "count"])
    for cTCounter, cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            hMeasurements = filterMeasurementsForTimePeriod(cT.hMeasurements, timePeriod, cT).exclude(count=float('nan')).values ('date', 'count', "hour")
            for hM in hMeasurements:
                writer.writerow([cT.sensor.ref, cT.modality.name, cT.isReverseChannel, timePeriodCounter, hM['date'].strftime ("%Y-%m-%d"), hM['hour'], hM['count']])
    return response
    
# extraction of the data for the basePopulation (if isBase is selected for some sensor in the frontend)
def getBasePopulation (timePeriods, basePopulationSensorRef, hourly):
    if not basePopulationSensorRef:
        return None
    cSensor = app.models.Sensor.objects.filter (ref=basePopulationSensorRef).first ()
    if not cSensor:
        return None
    res = {}
    for timePeriodCounter, timePeriod in enumerate(timePeriods):
        if hourly:
            res[timePeriodCounter] = defaultdict (lambda: defaultdict(float))
            for cT in cSensor.tracks.all ():
                measurements = filterMeasurementsForTimePeriod(cT.hMeasurements, timePeriod, cT).exclude(count=float('nan')).values ('date', 'count', "hour")
                for dM in measurements:
                    res[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")][dM['hour']] += dM['count']
            for d in res[timePeriodCounter]:
                res[timePeriodCounter][d] = {k:v for k,v in res[timePeriodCounter][d].items() if v != 0}
            res[timePeriodCounter] = {k:v for k,v in res[timePeriodCounter].items() if len(v) > 0}
        else:
            res[timePeriodCounter] = defaultdict (float)
            for cT in cSensor.tracks.all ():
                measurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum')
                for dM in measurements:
                    res[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")] += dM['count_sum']
            res[timePeriodCounter] = {k:v for k,v in res[timePeriodCounter].items() if v != 0}
    return res    
    
# the following views all have the same params - configuration of the sensors/timewindows + interface params like language
# they create a collection of primitive views to show in the frontend in the dedicated tab of the analysis page

# summary: raw graph + basic statistics
def getSummaryView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, False)
    respContent = []
    lines = []
    stats = []
    percentiles = [5, 25, 50, 75, 95]
    dateToTrackToCount = defaultdict(lambda: [0]*len(cTs)*len(timePeriods))
    for cTCounter, cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            if basePopulation:
                dMeasurements = [{'date':dM['date'], 'count_sum': dM['count_sum'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]} for dM in dMeasurements if dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]]
            for dM in dMeasurements:
                dateToTrackToCount[dM['date'].strftime ("%Y-%m-%d")][cTCounter * len(timePeriods) + timePeriodCounter] = dM['count_sum']
            if len (dMeasurements) == 0:
                continue
            values = [dM['count_sum'] for dM in dMeasurements]
            stats.append ([cT.nameForGraph (timePeriodCounter, withSensorRefs)] + [formatFloat (np.mean (values))] + [formatFloat (val) for val in np.percentile (values, percentiles).tolist()] + [formatFloat (np.std (values))])
            lines.append ({
                "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in dMeasurements],
                "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                "colorCounter": cTCounter,
                "timePeriodCounter": timePeriodCounter
            })
    respContent.append ({
        "type": 'lineChart',
        "title": getTranslatedString ('Total daily counts', lang) + (getTranslatedString (" (divided by the corresponding count of your selected base sensor)", lang) if basePopulation else ""),
        "subtitle":  getTranslatedString ('The following graph is the raw dataset we are working with.', lang),
        "xAxisType": 'time',
        "lines":lines
    })
    respContent.append ({
        "type": 'table',
        "title": getTranslatedString ('Statistics', lang),
        "subtitle":  getTranslatedString ('Here you can find some pre-calculated statistics for a quick overview.', lang),
        "captions": ['Dataset', 'Average'] + [getTranslatedString ("Percentile ", lang) + str (p) for p in percentiles] + [getTranslatedString ('Standard deviation', lang)],
        "lines":stats,
        "collapsed": True
    })
    return respContent

# sensors split: relative counts for selected sensors
def getSplitView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    respContent = []
    dateToTrackToCount = defaultdict(lambda: [0]*len(cTs)*len(timePeriods))
    for cTCounter, cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            for dM in dMeasurements:
                dateToTrackToCount[dM['date'].strftime ("%Y-%m-%d")][cTCounter * len(timePeriods) + timePeriodCounter] = dM['count_sum']
    if len(cTs) > 1:
        lines = []
        for cTCounter, cT in enumerate (cTs):
            for timePeriodCounter, timePeriod in enumerate(timePeriods):
                lines.append ({
                        "data": [{"x":dateString, "y":100 * sum (dateToTrackToCount[dateString][:cTCounter * len(timePeriods) + timePeriodCounter + 1]) / sum (dateToTrackToCount[dateString])} for dateString in sorted (dateToTrackToCount.keys()) if sum (dateToTrackToCount[dateString]) > 0],
                        "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                        "fill": str(-len(timePeriods)) if cTCounter >= 1 else "origin",
                        "colorCounter": cTCounter,
                        "timePeriodCounter": timePeriodCounter,
                        "showLine": True,
                    })
        respContent.append ({
            "type": 'scatterChart',
            "title": getTranslatedString ('The split of counts between different sensor-modalities combinations', lang),
            "subtitle":  getTranslatedString ('''Here we look at each day and the counts for sensor-modalities combinations available at that day. For each of the combination we show the percentage of the total count it represents.<br/>Here are some use cases for this view:<br/> - Getting the modal split: if you select a single sensor with different modalities available, the graph will directly show you the modal split<br/> - Comparing pairs of sensors: if you have a pair of nearby sensors, measuring the same modality, selecting those permits you to directly see and quantify how much of the data one sensor sees compared to the other. In an ideal situation and for the sensors located at the same place you should have a straight line at 50%.''', lang),
            "xAxisType": 'time',
            "lines":lines,
            "yAxisStep": 10,
            "yAxisMin": 0,
            "yAxisMax": 100,


        })
    else:
        respContent.append ({
                "type": 'text',
                "title": getTranslatedString ('At least 2 sensors or modalities are needed', lang),
                "subtitle":  getTranslatedString ('As here we want to see the percentage each sensor-modality combination counts, please select at least 2 of them in the left menu', lang),
                "isError": True
        })
    return respContent

# visualisation of number of counts returned by the sensor + tests scores
def getDataQualityView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    respContent = []
    respContent.append ({
        "type": 'lineChart',
        "title": getTranslatedString ('How stably the sensors are working?', lang),
        "subtitle": getTranslatedString ('''We work with different sensors and by construction they can have different properties: for example some can only work during the daylight while others are well working during the night as well. No matter how reliable is the sensor, it can also have some issues, preventing it from the normal functioning.<br/>
                       In order to see how reliable the data we are working with is, for each sensor we look at the number of hourly counts it is generating. Our goal is to have it stable in time (no anomalies). To automate this process, we perform the following checks: <br/>
                       - MinThreshold <span class="questionMark">?<div class="hint">A basic test, verifying that we have at least 3 counts per day</div></span><br/>
                       - PerformanceThreshold <span class="questionMark">?<div class="hint">Only used for sensors having at least 15 days of measurements. Here we are working with a dynamical system, looking at the number of measurements itself, but also at different percentiles of the rolling windows around the date. And we are checking some rules based on these values. For example: if the number of measurements at a particular date is higher than 85% of measurements in the interval [date - 15 days; date + 15 days], that is a valid point, etc.</div></span><br/>
                       - DBSCAN <span class="questionMark">?<div class="hint">The idea here is to look at all the historical data, see what values (numbers of measurements) were observed and create clusters from them (connect the values which are close, in our case differing by one from each other) and check the cluster size (number of days, falling in each cluster). We are using a machine learning algorithm for that, which explains the name <a target="_blank" href="https://en.wikipedia.org/wiki/DBSCAN">DBSCAN</a></div></span><br/>
                       - AllTests is valid when all of the above tests are valid<br/>
                       On the graph below, you can find the number of hourly counts at each day. Color of the point represents the number of succeeded tests and if you hover on top of it, you can see the details.<br/>
                       <b>You can filter out the days, not passing some of the tests in the time-window configuration on the left.</b><br/>
                       That will influence all the graphs we are working with. If you want to see exactly, how it impacts you can create a time window with and without data quality tests filtering to see its impact on the findings.
                       ''', lang),
        "xAxisType": 'time',
        "lines":[]
    })  
    for cTCounter, cT in enumerate(cTs):
        qualityValidationResults = cT.qualityValidationResults.values ('date', 'test__name', "passed")
        testNames = sorted (set ([r['test__name'] for r in qualityValidationResults]))
        qualityValidationResultsDic = defaultdict (dict)
        for qvr in qualityValidationResults:
            qualityValidationResultsDic[qvr['date']][qvr['test__name']] = qvr["passed"]
        
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum', "count")
            tooltips = [[test + ": " + str(qualityValidationResultsDic[dm['date']][test]  ) for test in testNames]  for dm in dMeasurements]
            passedRatios = [sum (qualityValidationResultsDic[dm['date']].values()) for dm in dMeasurements]
            colors = ['RGB(' + str(int (255-255*(pr / len(testNames)))) + ',' + str(int (255*(pr / len(testNames)))) + ',0)' for pr in passedRatios]
            respContent[0]["lines"].append ({
                "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count']} for dM in dMeasurements],
                "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                "tooltips": tooltips,
                "pointColors": colors,
                "colorCounter": cTCounter,
                "timePeriodCounter": timePeriodCounter
            })
    return respContent

# full hourly data analysis tab:
# averaged (wrt the observation window) counts at a particular hour --- "typical day"
# for each hour:
# - graph of evolution at different dates
# - if 2 or more timePeriods - statistically significant difference tests with map and table visualisations
def getDailyProfilesView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, True)
    respContent = []
    respContent.append ({
        "type": 'scatterChart',
        "title": getTranslatedString ('Average counts at an hour', lang),
        "subtitle": getTranslatedString ('Here for each modality and each time window we calculate the average counts per hour', lang) + (getTranslatedString (" and divide them by the corresponding count of your selected base sensor", lang) if basePopulation else "") + getTranslatedString ('. Hover at the point to see the number of days, which were available for the configured time window.', lang),
        "xAxisType": 'linear',
        "xAxisStep": 1,
        "lines":[]
    })
    noDataTracks = []
    noDataWithBaseTracks = []
    for cTCounter,cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            hMeasurements = filterMeasurementsForTimePeriod(cT.hMeasurements, timePeriod, cT).exclude(count=float('nan')).values ('date', 'count', "hour")
            if len (hMeasurements) == 0:
                noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            else:
                if basePopulation:
                    hMeasurements = [{'date':dM['date'], 'hour':dM['hour'], 'count': dM['count'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")][dM['hour']]} for dM in hMeasurements if (dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]) and (dM['hour'] in basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]) ]
                if len (hMeasurements) == 0:
                    noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                else:
                    hToDateMeasurements = defaultdict (list)
                    for hm in hMeasurements:
                        hToDateMeasurements[hm['hour']].append (hm)

                    data = []
                    tooltips = []
                    for h in sorted (hToDateMeasurements.keys ()):
                        mean = np.mean ([hm['count'] for hm in hToDateMeasurements[h]])
                        data.append ({"x":h, "y": mean})
                        tooltips.append (["Mean: " + str (mean), "Based on " + str (len(hToDateMeasurements[h])) + ' samples', cT.nameForGraph (timePeriodCounter, withSensorRefs)])
                    
                    respContent[0]["lines"].append ({
                        "data": data,
                        "showLine": True,
                        "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                        "tooltips": tooltips,
                        "colorCounter": cTCounter,
                        "timePeriodCounter": timePeriodCounter
                        #"pointColors": colors
                    })
    if len(noDataWithBaseTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang),
                        "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                        "isError": True
                })
    if len(noDataTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data in the specified time window', lang),
                        "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                        "isError": True
                })
    perHour = {
            "type": 'selectable',
            "title": getTranslatedString ('Per hour information', lang),
            "subtitle": getTranslatedString ('Select the hour you are interested in to get more detailed information about it.', lang),
            "children":[]
        }
    for h in range (24):
        cGraph = {
            "type": 'lineChart',
            "title": getTranslatedString ('Temporal evolution', lang),
            "subtitle": getTranslatedString ("Here you see how the total count", lang) + (getTranslatedString (" divided by the corresponding count of your selected base sensor", lang) if basePopulation else "") + getTranslatedString (" during the selected hour changed for different days", lang),
            "xAxisType": 'time',
            "lines":[]
        }
        noDataTracks = []
        noDataWithBaseTracks = []
        hasData = False
        allMeasurements = []
        for cTCounter, cT in enumerate(cTs):
            allMeasurements.append ({'track': cT, 'measurements': []})
            for timePeriodCounter, timePeriod in enumerate(timePeriods):
                hMeasurements = filterMeasurementsForTimePeriod(cT.hMeasurements, timePeriod, cT).filter (hour=h).exclude(count=float('nan')).values ('date', 'count')
                if len (hMeasurements) == 0:
                    noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                else:
                    if basePopulation:
                        hMeasurements = [{'date':dM['date'], 'count': dM['count'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")][h]} for dM in hMeasurements if (dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]) and (h in basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]) ]
                    if len (hMeasurements) == 0:
                        noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                    else:
                        hasData = True
                        allMeasurements[-1]['measurements'].append ((timePeriodCounter, [d['count'] for d in hMeasurements] ))
                        cGraph["lines"].append ({
                            "data": [{"x":hm['date'].strftime ("%Y-%m-%d") + " " + str(h) + ":00:00", "y":hm["count"]} for hm in hMeasurements],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                            #"tooltips": tooltips,
                            #"pointColors": colors
                        }) 
        if hasData:
            cHour = {
                "title": getTranslatedString ('Analysis of the data between {h}:00 and {hp1}:00', lang).format(h = str(h), hp1 = str ((h + 1) % 24)),
                "type": 'list',
                "children":[cGraph]
            }
            if len(noDataWithBaseTracks) > 0:
                cHour['children'].insert (0, {
                                "type": 'text',
                                "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang) + getTranslatedString (' for this hour', lang),
                                "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                                "isError": True
                        })
            if len(noDataTracks) > 0:
                cHour['children'].insert (0, {
                                "type": 'text',
                                "title": getTranslatedString ('No data in the specified time window', lang) + getTranslatedString (' for this hour', lang),
                                "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                                "isError": True
                        })
            if len (timePeriods) == 1:
                cHour['children'].append ({
                                "type": 'text',
                                "title": getTranslatedString ('Please add more time windows for comparative analysis', lang),
                                "subtitle": getTranslatedString ("If you configure at least 2 time windows at the left panel, we can check how the signal from sensors compares between them", lang),
                        })
            else:
                sig = 0
                nSig = 0
                sensorRefToDifference = {}
                for cMeasurement in allMeasurements:
                    cMeasurement['stats'] = []
                    for ic, aM in enumerate(cMeasurement["measurements"]):
                        for aM2 in cMeasurement["measurements"][ic + 1:]:
                            #print (aM, aM2)
                            if (len (aM[1]) > 0) and (len(aM2[1]) > 0):
                                stat = (aM, aM2, kstest (aM[1], aM2[1])[1])
                                cMeasurement['stats'].append (stat)
                                if cMeasurement['track'].sensor.ref not in sensorRefToDifference:
                                    sensorRefToDifference[cMeasurement['track'].sensor.ref] = { "sig": 0, "nsig": 0, "details": [], "meanDiffScore": 0}
                                sensorRefToDifference[cMeasurement['track'].sensor.ref]['details'].append (
                                        cMeasurement['track'].modality.name + (" reverse" if cMeasurement['track'].isReverseChannel else "") + 
                                        ((str(stat[0][0] + 1) + " - " + str(stat[1][0] + 1)) if len(timePeriods) > 2 else "") + " p-value: " + "{:.3f}".format( stat[2])
                                        )
                                if cMeasurement['stats'][-1][-1] <= pThreshold:
                                    sensorRefToDifference[cMeasurement['track'].sensor.ref]['sig'] += 1
                                    mean1 = np.mean(stat[0][1])
                                    mean2 = np.mean(stat[1][1])
                                    sensorRefToDifference[cMeasurement['track'].sensor.ref]['details'][-1] += " mean " + formatFloat (mean1) + " vs " + formatFloat (mean2)
                                    sensorRefToDifference[cMeasurement['track'].sensor.ref]['meanDiffScore'] += 1 if mean2 > mean1 else -1
                                    sig += 1
                                else:
                                    sensorRefToDifference[cMeasurement['track'].sensor.ref]['nsig'] += 1
                                    nSig += 1
                if len(sensorRefToDifference) > 0:
                    cHour['children'].append ({
                        "type": 'map',
                        "title": getTranslatedString ('Map of differences', lang),
                        "subtitle": getTranslatedString ('''Our goal here is to compare how the traffic has evolved between selected time windows.<br/>
                                                            To do so, we perform the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for each sensor track (separately for each modality / direction). <br/>
                                                            Colors of the sensors represent the outcomes:<br/>
                                                            - <span style="color:#ff0000">Red</span> means that for the majority of modality/direction pairs the traffic became <b>more intense</b><br/>
                                                            - <span style="color:#00ff00">Green</span> means that for the majority of modality/direction pairs the traffic became <b>less intense</b><br/>
                                                            - <span style="color:#aaaaff">Purple</span> means that no statistically significant difference is observed or there is a balance between different modality/direction pairs<br/>
                                                            - <span style="color:#0000ff">Blue</span> means there is not enough data to make the comparative analysis<br/>
                                                            You can always hover on top of the sensor for more details''', lang),
                        "meta": sensorRefToDifference
                    })
                for diff in sensorRefToDifference.values ():
                    diff['detailsHtmlString'] = '<br/>'.join (diff['details'])
                    diff['detailsString'] = '\n'.join (diff['details'])
                    if diff['meanDiffScore'] > 0:
                        diff['color'] = 'ff0000'
                    elif diff['meanDiffScore'] < 0:
                        diff['color'] = '00ff00'
                    else:
                        diff['color'] = 'aaaaff'
                if sig > 0:
                    tableLines = []
                    for cMeasurement in allMeasurements:
                        segmentTitle = cMeasurement['track'].sensor.ref + ' ' + cMeasurement['track'].modality.name + (" reverse" if cMeasurement['track'].isReverseChannel else "")
                        for stat in cMeasurement['stats']:
                            if stat[-1] <= pThreshold:
                                tableLines.append ([segmentTitle] + ([stat[0][0] + 1, stat[1][0] + 1] if len(timePeriods) > 2 else []) + ["{:.3f}".format( stat[2]), formatFloat (np.mean(stat[0][1])), formatFloat (np.mean(stat[1][1]))])
                                segmentTitle = ""
                    cHour['children'].append ({
                        "type": 'table',
                        "title": getTranslatedString ('Sensors with significant difference', lang),
                        "subtitle": getTranslatedString ('For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives small p-values (below {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can confidently say that the signals observed are significantly different.', lang).format(pThr = pThreshold),
                        "captions": [getTranslatedString ('Sensor', lang)] + ([getTranslatedString ('Time window', lang) + ' 1', getTranslatedString ('Time window', lang) + ' 2'] if len(timePeriods) > 2 else []) + ['p-value', getTranslatedString ('mean', lang) + ' 1', getTranslatedString ('mean', lang) + ' 2'],
                        "lines":tableLines
                    })
                if nSig > 0:
                    tableLines = []
                    for cMeasurement in allMeasurements:
                        segmentTitle = cMeasurement['track'].sensor.ref + ' ' + cMeasurement['track'].modality.name + (" reverse" if cMeasurement['track'].isReverseChannel else "")
                        for stat in cMeasurement['stats']:
                            if stat[-1] > pThreshold:
                                tableLines.append ([segmentTitle] + ([stat[0][0] + 1, stat[1][0] + 1] if len(timePeriods) > 2 else []) + ["{:.3f}".format( stat[2])])
                                segmentTitle = ""

                    cHour['children'].append ({
                        "type": 'table',
                        "title": getTranslatedString ('Sensors without significant difference', lang),
                        "subtitle": getTranslatedString ('''For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives big p-values (above {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can NOT confidently say that the signals observed are significantly different.''', lang).format (pThr = pThreshold),
                        "captions": [getTranslatedString ('Sensor', lang)] + ([getTranslatedString ('Time window', lang) + ' 1', getTranslatedString ('Time window', lang) + ' 2'] if len(timePeriods) > 2 else []) + ['p-value'],
                        "lines":tableLines
                    })
            perHour['children'].append ({"label": str (h) + ":XX", "item": cHour})
    respContent.append (perHour)
    return respContent

# split in trend/weekly/residuals graphs
def getTrendView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, False)
    respContent = []
    lines = []
    trends = []
    seasonals = []
    residuals = []
    hadNotEnoughData = []
    noDataTracks = []
    noDataWithBaseTracks = []
    for cTCounter, cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            if len (dMeasurements) == 0:
                noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            else:
                if basePopulation:
                    dMeasurements = [{'date':dM['date'], 'count_sum': dM['count_sum'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]} for dM in dMeasurements if dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]]
                if len (dMeasurements) == 0:
                    noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                else:
                    lines.append ({
                            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in dMeasurements],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                        }) 
                    if len (dMeasurements) >= 14:
                        decompose, reconstructedDF = getTrueSeasonalDecompose (dMeasurements)
                        trends.append ({
                            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['trend']} for _ , dM in decompose.iterrows()],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                        })
                        seasonals.append ({
                            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['seasonal']} for _ , dM in decompose.iterrows()],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                        })
                        residuals.append ({
                            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['resid']} for _ , dM in decompose.iterrows()],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                        })
                    else:
                        hadNotEnoughData.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))       
    if len (lines) > 0:
        respContent.append ({
            "type": 'lineChart',
            "title": getTranslatedString ('Total daily counts', lang) + (getTranslatedString (" (divided by the corresponding count of your selected base sensor)", lang) if basePopulation else ""),
            "subtitle":  getTranslatedString ('''The following graph is the raw dataset we are working with.''', lang),
            "xAxisType": 'time',
            "lines":lines
        })
        trendAnalysis = {
            "title": "",
            "subtitle": getTranslatedString ('''From raw data using a one-dimensional convolution <a target="_blank" href="https://en.wikipedia.org/wiki/Kernel_(image_processing)"><span class="questionMark">?</span></a> we are extracting the trend component of the signal. <br/>
                            When the trend is deducted from the signal, we find a weekly periodical component (weekly patterns) and the remaining part is called a residual.<br/>
                            You can see all these components in the next graphs.<br/>
                            <b>Please consider external effects before drawing conclusions: for example for some sensors the decrease/increase in the trend can be related with the meteo conditions or the daylight duration''', lang),
            "type": 'list',
            "children":[]
        }
        if len(hadNotEnoughData) > 0:
            trendAnalysis['children'].append ({
                "type": 'text',
                "title": getTranslatedString ('Issue found', lang),
                "subtitle": getTranslatedString ('The following datasets have less than 14 daily measures, which are required to make the temporal decomposition and they are thus removed: <br/>', lang) + "<br/>".join (hadNotEnoughData),
                "isError": True
            })
        if len (trends) > 0:
            trendAnalysis['children'].append ({
                "type": 'lineChart',
                "title": 'Trend',
                "xAxisType": 'time',
                "lines":trends
            })
            trendAnalysis['children'].append ({
                "type": 'lineChart',
                "title": 'Weekly patterns',
                "xAxisType": 'time',
                "lines":seasonals
            })
            trendAnalysis['children'].append ({
                "type": 'scatterChart',
                "title": 'Residuals',
                "xAxisType": 'time',
                "lines":residuals
            })
        else:
            trendAnalysis['children'].append ({
                "type": 'text',
                "title": getTranslatedString ('Issue found', lang),
                "subtitle": getTranslatedString ('Datasets have less than 14 daily measures, which are required to make the temporal decomposition and thus are not shown.', lang)
            })
        respContent.append (trendAnalysis)
        if len(noDataWithBaseTracks) > 0:
            respContent.insert (0, {
                            "type": 'text',
                            "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang),
                            "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                            "isError": True
                    })
        if len(noDataTracks) > 0:
            respContent.insert (0, {
                            "type": 'text',
                            "title": getTranslatedString ('No data in the specified time window', lang),
                            "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                            "isError": True
                    })
    else:
        respContent.append  ({
                "type": 'text',
                "title": getTranslatedString ('Issue found', lang),
                "subtitle": getTranslatedString ('No data found, please check the modalities selection and the time windows configuration', lang),
                "isError": True
            }) 
    return respContent

# statistical tests for difference on a daily level for 2 time periods
def getDailyLevelDifferenceView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, False)
    respContent = []
    lines = []   
    representativityAnalysisDiff = {
                    "type": 'table',
                    "title": getTranslatedString ('Sensors with significant difference', lang),
                    "subtitle": getTranslatedString ('For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives small p-values (below {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can confidently say that the signals observed are significantly different.', lang).format(pThr = pThreshold),
                    "captions": [getTranslatedString ('Sensor', lang)] + ([getTranslatedString ('Time window', lang) + ' 1', getTranslatedString ('Time window', lang) + ' 2'] if len(timePeriods) > 2 else []) + ['p-value', getTranslatedString ('mean', lang) + ' 1', getTranslatedString ('mean', lang) + ' 2'],
                    "lines":[]
                }
    representativityAnalysisNDiff = {
                    "type": 'table',
                    "title": getTranslatedString ('Sensors without significant difference', lang),
                    "subtitle": getTranslatedString ('''For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives big p-values (above {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can NOT confidently say that the signals observed are significantly different.''', lang).format (pThr = pThreshold),
                    "captions": [getTranslatedString ('Sensor', lang)] + ([getTranslatedString ('Time window', lang) + ' 1', getTranslatedString ('Time window', lang) + ' 2'] if len(timePeriods) > 2 else []) + ['p-value'],
                    "lines":[]
                }
    representativityAnalysisRefToDifference = {}
    representativityAnalysis = {"title": "",
            "subtitle": getTranslatedString ('''Here we verify if the behaviour for each sensor track inside one time window is similar to the other time window.
                                                That is done on the total daily counts.<br/>
                                                Usually it makes sense to configure a short time window and a long one and to see how representable the short one is.<br/>
                                                If one time window is inside the other one, keep an eye on p-values more closely: even a bit higher p-values can represent a significant difference as we are including the overlapping counts in both datasets.''', lang),
            "type": 'list',
            "children":[]}
    if len (timePeriods) != 2:
        representativityAnalysis['children'].append ({
                "type": 'text',
                "title": getTranslatedString ('Issue found', lang),
                "subtitle": getTranslatedString ('Please configure exactly 2 time windows for this type of analysis', lang),
                "isError": True
            })
    noDataTracks = []
    noDataWithBaseTracks = []
    for cTCounter, cT in enumerate(cTs):
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            if len (dMeasurements) == 0:
                noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            else:
                if basePopulation:
                    dMeasurements = [{'date':dM['date'], 'count_sum': dM['count_sum'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]} for dM in dMeasurements if dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]]
                    if len (dMeasurements) == 0:
                        noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            lines.append ({
                    "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in dMeasurements],
                    "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                    "colorCounter": cTCounter,
                    "timePeriodCounter": timePeriodCounter
                })             
            if len (timePeriods) == 2:
                if timePeriodCounter == 0:
                    prevTWMeasurements = dMeasurements
                else:
                    aM = [d['count_sum'] for d in prevTWMeasurements]
                    aM2 = [d['count_sum'] for d in dMeasurements]
                    if (len (aM) > 0) and (len (aM2) > 0):
                        ks = kstest (aM, aM2)[1]
                        segmentTitle = cT.modality.name + (" reverse" if cT.isReverseChannel else "")
                        if cT.sensor.ref not in representativityAnalysisRefToDifference:
                            representativityAnalysisRefToDifference[cT.sensor.ref] = { "sig": 0, "nsig": 0, "details": [], "meanDiffScore": 0}
                        representativityAnalysisRefToDifference[cT.sensor.ref]['details'].append (segmentTitle + " p-value: " + "{:.3f}".format(ks))
                        if ks <= pThreshold:
                            mean1 = np.mean(aM)
                            mean2 = np.mean(aM2)
                            representativityAnalysisDiff['lines'].append ([cT.sensor.ref + " " + segmentTitle] + ["{:.3f}".format(ks), formatFloat (mean1), formatFloat (mean2)])
                            representativityAnalysisRefToDifference[cT.sensor.ref]['sig'] += 1
                            representativityAnalysisRefToDifference[cT.sensor.ref]['details'][-1] += " mean " + formatFloat (mean1) + " vs " + formatFloat (mean2)
                            representativityAnalysisRefToDifference[cT.sensor.ref]['meanDiffScore'] += 1 if mean2 > mean1 else -1
                        else:
                            representativityAnalysisNDiff['lines'].append ([cT.sensor.ref + " " + segmentTitle] + ["{:.3f}".format(ks)])
                            representativityAnalysisRefToDifference[cT.sensor.ref]['nsig'] += 1           
    if len (lines) > 0:
        respContent.append ({
            "type": 'lineChart',
            "title": getTranslatedString ('Total daily counts', lang) + (getTranslatedString (" (divided by the corresponding count of your selected base sensor)", lang) if basePopulation else ""),
            "subtitle":  getTranslatedString ('''The following graph is the raw dataset we are working with.''', lang),
            "xAxisType": 'time',
            "lines":lines
        })
        for diff in representativityAnalysisRefToDifference.values ():
            diff['detailsHtmlString'] = '<br/>'.join (diff['details'])
            diff['detailsString'] = '\n'.join (diff['details'])
            if diff['meanDiffScore'] > 0:
                diff['color'] = 'ff0000'
            elif diff['meanDiffScore'] < 0:
                diff['color'] = '00ff00'
            else:
                diff['color'] = 'aaaaff'
        if len(representativityAnalysisRefToDifference) > 0:
            representativityAnalysis['children'].append ({
                "type": 'map',
                "title": getTranslatedString ('Map of differences', lang),
                "subtitle": getTranslatedString ('''Our goal here is to compare how the traffic has evolved between selected time windows.<br/>
                                                            To do so, we perform the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for each sensor track (separately for each modality / direction). <br/>
                                                            Colors of the sensors represent the outcomes:<br/>
                                                            - <span style="color:#ff0000">Red</span> means that for the majority of modality/direction pairs the traffic became <b>more intense</b><br/>
                                                            - <span style="color:#00ff00">Green</span> means that for the majority of modality/direction pairs the traffic became <b>less intense</b><br/>
                                                            - <span style="color:#aaaaff">Purple</span> means that no statistically significant difference is observed or there is a balance between different modality/direction pairs<br/>
                                                            - <span style="color:#0000ff">Blue</span> means there is not enough data to make the comparative analysis<br/>
                                                            You can always hover on top of the sensor for more details''', lang),
                "meta": representativityAnalysisRefToDifference
            })
        if len(representativityAnalysisDiff['lines']) > 0:
            representativityAnalysis['children'].append (representativityAnalysisDiff)
        if len(representativityAnalysisNDiff['lines']) > 0:
            representativityAnalysis['children'].append (representativityAnalysisNDiff)
        respContent.append (representativityAnalysis)
        if len(noDataWithBaseTracks) > 0:
            respContent.insert (0, {
                            "type": 'text',
                            "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang),
                            "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                            "isError": True
                    })
        if len(noDataTracks) > 0:
            respContent.insert (0, {
                            "type": 'text',
                            "title": getTranslatedString ('No data in the specified time window', lang),
                            "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                            "isError": True
                    })
    else:
        respContent.append  ({
                "type": 'text',
                "title": getTranslatedString ('Issue found', lang),
                "subtitle": getTranslatedString ('No data found, please check the modalities selection and the time windows configuration', lang),
                "isError": True
            })
    return respContent

# temporal extrapolation (uses timePeriod 1 to extrapolate to timePeriod 2) based on a single track
def getSSExtrapolationView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    if len (timePeriods) != 2:
        return [{
                "type": 'text',
                "title": getTranslatedString ('Incorrect time windows count', lang),
                "subtitle": getTranslatedString ('Please configure exactly 2 time windows for this type of analysis', lang),
                "isError": True
            }]
    tp1From, tp1To = getFromToFromTimePeriod (timePeriods[0])
    tp2From, tp2To = getFromToFromTimePeriod (timePeriods[1])
    if tp2From <= tp1From:
        return [{
            "type": 'text',
            "title": getTranslatedString ('Incorrect time window configuration', lang),
            "subtitle": getTranslatedString ("We only predict to the future based on historical data, thus time window 2 can't be partially before the time window 1. Please correct", lang),
            "isError": True
        }]
    if tp1To < tp1From:
        return [{
            "type": 'text',
            "title": getTranslatedString ('Incorrect time window configuration', lang),
            "subtitle": getTranslatedString ("Time window 1 ends before its start. Please correct", lang),
            "isError": True
        }]
    if tp2To < tp2From:
        return [{
            "type": 'text',
            "title": getTranslatedString ('Incorrect time window configuration', lang),
            "subtitle": getTranslatedString ("Time window 2 ends before its start. Please correct", lang),
            "isError": True
        }]
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, False)
    respContent = []
    ssExtrapolationHadNotEnoughData = False
    ssExtrapolationLines = []
    allMeasurements = []
    noDataTracks = []
    noDataWithBaseTracks = []
    notEnoughData = []
    for cTCounter, cT in enumerate(cTs):
        allMeasurements.append ([])
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            allMeasurements[-1].append (dMeasurements)
            if len (dMeasurements) == 0:
                noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            else:
                if basePopulation:
                    dMeasurements = [{'date':dM['date'], 'count_sum': dM['count_sum'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]} for dM in dMeasurements if dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]]
                if len (dMeasurements) == 0:
                    noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                else:
                    if timePeriodCounter == 0:  
                        if (len (dMeasurements) >= 14) and (tp2From.date () > min (dM['date'] for dM in dMeasurements)):
                            decompose, reconstructedDF = getTrueSeasonalDecompose (dMeasurements)
                            ssExtrapolationLines.append ({
                                "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in dMeasurements],
                                "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                                "colorCounter": cTCounter,
                                "timePeriodCounter": timePeriodCounter
                            })
                            model = SARIMAX(reconstructedDF['countSum'], order=(0,1,0),seasonal_order=(1,1,1,7), freq='D').fit(disp=0)
                            prediction = model.predict (start=tp2From.strftime ("%Y-%m-%d"), end=tp2To.strftime ("%Y-%m-%d"))
                            ssExtrapolationLines.append ({
                                "data": [{"x":k.strftime ("%Y-%m-%d"), "y":v} for k,v in prediction.items()],
                                "label": cT.nameForGraph (timePeriodCounter + 1, withSensorRefs) + " prediction",
                                "colorCounter": cTCounter,
                                "timePeriodCounter": 2
                            })
                        else:
                            notEnoughData.append (cT.nameForGraph (-1, withSensorRefs))
                    else:
                        ssExtrapolationLines.append ({
                            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in dMeasurements],
                            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                            "colorCounter": cTCounter,
                            "timePeriodCounter": timePeriodCounter
                            })
    if len(ssExtrapolationLines) > 0:
        respContent.append ({
            "type": 'lineChart',
            "title": getTranslatedString ('Total daily counts', lang) + (getTranslatedString (" (divided by the corresponding count of your selected base sensor)", lang) if basePopulation else ""),
            "subtitle": getTranslatedString ('''Here we use the information from the time window 1 to extrapolate the signal to the time window 2. <br/>
                                                Each sensor track is treated separately.<br/>
                                                If there is any data available for time window 2 it is also shown for comparison.
                                                Extrapolation itself is done using the SARIMAX methodology <span class="questionMark">?<div class="hint">The method belongs to the <a href="https://en.wikipedia.org/wiki/Autoregressive_integrated_moving_average" target="_blank">Autoregressive integrated moving average</a> family. This method tries to learn how the signal evolves and pays attention to both the seasonality effects (weekly patterns in our case) and the so-called non-stationarity (the fact that average values can evolve in time - have a look at the trend analysis tab). For more details it is better to check the link in this popup</div></span><br/>
                                                <b>This type of extrapolation is only useful for short-term predictions. As it doesn't have any external corrections, long-term extrapolations usually increase or decrease unreasonably</b>''', lang),
            "xAxisType": 'time',
            "lines":ssExtrapolationLines
        })
    if len(notEnoughData) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('Not enough data in time window 1', lang),
                        "subtitle": getTranslatedString ("For the following sensors in the timewindow 1 we have less than 14 days of measurements, which are needed for extrapolation: <br/>", lang) + "<br/>".join (notEnoughData),
                        "isError": True
                })
    if len(noDataWithBaseTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang),
                        "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                        "isError": True
                })
    if len(noDataTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data in the specified time window', lang),
                        "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                        "isError": True
                })
    return respContent
    
# temporal extrapolation (uses timePeriod 1 to extrapolate to timePeriod 2) based on a the track history + information from other tracks
# with and without weekly patterns imposed
def getMSExtrapolationView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang):
    if len (timePeriods) != 2:
        return [{
                "type": 'text',
                "title": getTranslatedString ('Incorrect time windows count', lang),
                "subtitle": getTranslatedString ('Please configure exactly 2 time windows for this type of analysis', lang),
                "isError": True
            }]
    if len (cTs) < 2:
        return [{
                "type": 'text',
                "title": getTranslatedString ('Insufficient number of sensor tracks selected', lang),
                "subtitle": getTranslatedString ('Please select at least 2 sensor tracks for this type of analysis', lang),
                "isError": True
            }]
    tp1From, tp1To = getFromToFromTimePeriod (timePeriods[0])
    tp2From, tp2To = getFromToFromTimePeriod (timePeriods[1])
    if tp2From <= tp1From:
        return [{
            "type": 'text',
            "title": getTranslatedString ('Incorrect time window configuration', lang),
            "subtitle": getTranslatedString ("We only predict to the future based on historical data, thus time window 2 can't be partially before the time window 1. Please correct", lang),
            "isError": True
        }]
    basePopulation = getBasePopulation (timePeriods, basePopulationSensorRef, False)
    respContent = []
    msExtrapolation = {"title": "",
            "subtitle": getTranslatedString ('''Here we use the information from the time window 1 to extrapolate the signal to the time window 2. <br/>
                                                Each sensor track is predicted based on the information from other tracks.<br/>
                                                If there is any data available for time window 2 it is also shown for comparison.
                                                Extrapolation itself is done using the SARIMAX methodology with exogeneous factors<span class="questionMark">?<div class="hint">The method belongs to the <a href="https://en.wikipedia.org/wiki/Autoregressive_integrated_moving_average" target="_blank">Autoregressive integrated moving average</a> family. This method tries to learn how the signal evolves and pays attention to both the seasonality effects (weekly patterns in our case) and the so-called non-stationarity (the fact that average values can evolve in time - have a look at the trend analysis tab). For more details it is better to check the link in this popup</div></span>''', lang),
            "type": 'list',
            "children":[]}
    msExtrapolationLines = []  
    msExtrapolationLinesNoWeekly = []  
    allMeasurements = []
    noDataTracks = []
    noDataWithBaseTracks = []
    notEnoughData = []
    for cTCounter, cT in enumerate(cTs):
        allMeasurements.append ([])
        for timePeriodCounter, timePeriod in enumerate(timePeriods):
            dMeasurements = filterMeasurementsForTimePeriod(cT.dMeasurements, timePeriod, cT).values ('date', 'count_sum') 
            allMeasurements[-1].append (dMeasurements)
            if len (dMeasurements) == 0:
                noDataTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
            else:
                if basePopulation:
                    dMeasurements = [{'date':dM['date'], 'count_sum': dM['count_sum'] / basePopulation[timePeriodCounter][dM['date'].strftime ("%Y-%m-%d")]} for dM in dMeasurements if dM['date'].strftime ("%Y-%m-%d") in basePopulation[timePeriodCounter]]
                if len (dMeasurements) == 0:
                    noDataWithBaseTracks.append (cT.nameForGraph (timePeriodCounter, withSensorRefs))
                elif len (dMeasurements) < 14 and timePeriodCounter == 0:
                    notEnoughData.append (cT.nameForGraph (-1, withSensorRefs))
    for predictionTrackCounter in range(len (allMeasurements)):
        if len (allMeasurements[predictionTrackCounter][0]) < 14:
            continue
        cT = cTs[predictionTrackCounter]
        msExtrapolationLines.append ({
            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in allMeasurements[predictionTrackCounter][0]],
            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
            "colorCounter": predictionTrackCounter,
            "timePeriodCounter": 0
        })
        msExtrapolationLines.append ({
            "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in allMeasurements[predictionTrackCounter][1]],
            "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
            "colorCounter": predictionTrackCounter,
            "timePeriodCounter": 1
        })
        decompose, reconstructedDF = getTrueSeasonalDecompose (allMeasurements[predictionTrackCounter][0])
        supportDates = [[k for k, v in reconstructedDF['countSum'].items()]]
        supportDates.append (list(pd.date_range(start=max(supportDates[0]) + pd.DateOffset(1), end=tp2To.strftime ("%Y-%m-%d"), freq='D')))
        supportSeriesLists = [[],[]]
        supportLabels = []
        for supportTrackCounter in range (len(allMeasurements)):
            if supportTrackCounter == predictionTrackCounter:
                continue
            supportLabels.append (str(supportTrackCounter))
            if len(allMeasurements[supportTrackCounter][0]) > 0:
                mean = np.mean ([dM['count_sum'] for dM in allMeasurements[supportTrackCounter][0]]) 
            else:
                mean = np.mean ([dM['count_sum'] for dM in cTs[supportTrackCounter].dMeasurements.values ('count_sum')]) 
            for part in [0,1]:
                dateToCount = defaultdict(lambda:mean)
                for dM in allMeasurements[supportTrackCounter][part]:
                    dateToCount[(dM['date']).strftime ("%Y-%m-%d")] = dM['count_sum'] # - timedelta(days=1) !important! timedelta is shifting the date axis by 1 in order to use current value of the supporting track and not the previous one
                supportSeriesLists[part].append ([dateToCount[k.strftime ("%Y-%m-%d")] if k.strftime ("%Y-%m-%d") in dateToCount else (mean + randint (-1,1)) for k in supportDates[part]]) #randint is used to have some variability around the mean - otherwise arima fails.
        supportDataFrames = [ pd.DataFrame(np.column_stack(supportSeriesLists[part]), index=supportDates[part], columns=supportLabels) for part in [0,1] ]
        model = SARIMAX(reconstructedDF['countSum'], order=(0,1,0),seasonal_order=(1,1,1,7), freq='D', exog=supportDataFrames[0]).fit(disp=0)
        start = tp2From.strftime ("%Y-%m-%d") if tp2From >= min(supportDates[0]) else min(supportDates[0]).strftime ("%Y-%m-%d")
        prediction = model.predict (start=start, end=tp2To.strftime ("%Y-%m-%d"), exog=supportDataFrames[1])
        msExtrapolationLines.append ({
            "data": [{"x":k.strftime ("%Y-%m-%d"), "y":v} for k,v in prediction.items()],
            "label": cT.nameForGraph (timePeriodCounter + 1, withSensorRefs) + " prediction",
            "colorCounter": predictionTrackCounter,
            "timePeriodCounter": 2
        })
    emptyTracks = []
    for predictionTrackCounter in range(len (allMeasurements)):
        cT = cTs[predictionTrackCounter]
        if len (allMeasurements[predictionTrackCounter][0]) < 3:
            emptyTracks.append (cT.nameForGraph (-1, withSensorRefs))
        else:
            msExtrapolationLinesNoWeekly.append ({
                "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in allMeasurements[predictionTrackCounter][0]],
                "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                "colorCounter": predictionTrackCounter,
                "timePeriodCounter": 0
            })
            msExtrapolationLinesNoWeekly.append ({
                "data": [{"x":dM['date'].strftime ("%Y-%m-%d"), "y":dM['count_sum']} for dM in allMeasurements[predictionTrackCounter][1]],
                "label": cT.nameForGraph (timePeriodCounter, withSensorRefs),
                "colorCounter": predictionTrackCounter,
                "timePeriodCounter": 1
            })
            reconstructedDF = convertMeasurementsToDF (allMeasurements[predictionTrackCounter][0])
            supportDates = [[k for k, v in reconstructedDF['countSum'].items()]]
            supportDates.append (list(pd.date_range(start=max(supportDates[0]) + pd.DateOffset(1), end=tp2To.strftime ("%Y-%m-%d"), freq='D')))
            supportSeriesLists = [[],[]]
            supportLabels = []
            for supportTrackCounter in range (len(allMeasurements)):
                if supportTrackCounter == predictionTrackCounter:
                    continue
                supportLabels.append (str(supportTrackCounter))
                mean = np.mean ([dM['count_sum'] for dM in allMeasurements[supportTrackCounter][0]]) if len (allMeasurements[supportTrackCounter][0]) > 0 else 0
                for part in [0,1]:
                    dateToCount = defaultdict(lambda:mean)
                    for dM in allMeasurements[supportTrackCounter][part]:
                        dateToCount[(dM['date']).strftime ("%Y-%m-%d")] = dM['count_sum'] # - timedelta(days=1) !important! timedelta is shifting the date axis by 1 in order to use current value of the supporting track and not the previous one
                    supportSeriesLists[part].append ([dateToCount[k.strftime ("%Y-%m-%d")] for k in supportDates[part]])
            supportDataFrames = [ pd.DataFrame(np.column_stack(supportSeriesLists[part]), index=supportDates[part], columns=supportLabels) for part in [0,1] ]
            model = SARIMAX(reconstructedDF['countSum'], order=(0,1,0), freq='D', exog=supportDataFrames[0]).fit(disp=0)
            start = tp2From.strftime ("%Y-%m-%d") if tp2From >= min(supportDates[0]) else min(supportDates[0]).strftime ("%Y-%m-%d")
            prediction = model.predict (start=start, end=tp2To.strftime ("%Y-%m-%d"), exog=supportDataFrames[1])
            msExtrapolationLinesNoWeekly.append ({
                "data": [{"x":k.strftime ("%Y-%m-%d"), "y":v} for k,v in prediction.items()],
                "label": cT.nameForGraph (timePeriodCounter + 1, withSensorRefs) + " prediction",
                "colorCounter": predictionTrackCounter,
                "timePeriodCounter": 2
            })
    if len(msExtrapolationLines) > 0:
        msExtrapolation['children'].append ({
            "type": 'text',
            "title": getTranslatedString ('With weekly patterns', lang),
        })
        if len(notEnoughData) > 0:
            msExtrapolation['children'].append ({
                            "type": 'text',
                            "title": getTranslatedString ('Not enough data in time window 1', lang),
                            "subtitle": getTranslatedString ("For the following sensors in the timewindow 1 we have less than 14 days of measurements, which are needed for this extrapolation: <br/>", lang) + "<br/>".join (notEnoughData),
                            "isError": True
                    })
        msExtrapolation['children'].append ({
            "type": 'lineChart',
            "xAxisType": 'time',
            "lines":msExtrapolationLines
        })
    else:
        msExtrapolation['children'].append ({
                            "type": 'text',
                            "title": getTranslatedString ('Not enough data in time window 1 for the extrapolation with weekly patterns', lang),
                            "subtitle": getTranslatedString ("None of the sensors in the time window 1 have at least 14 days of measurements, which are needed for this extrapolation, so this part is removed", lang),
                            "isError": True
                    })
    if len(msExtrapolationLinesNoWeekly) > 0:
        msExtrapolation['children'].append ({
            "type": 'text',
            "title": getTranslatedString ('Without weekly patterns', lang),
            "subtitle":  getTranslatedString ('''Here we don't focus on the identification of weekly patterns. That can generate weaker predictions on the signals having a long time frame available, but the advantage is that we can also focus on the signals only available for a few days.<br/>If no sensor has observations anymore, the signal will converge to a horizontal line''', lang),
        })
        if len(emptyTracks) > 0:
            msExtrapolation['children'].append ({
                    "type": 'text',
                    "title": getTranslatedString ('Some sensors have not enough data in time window 1', lang),
                    "subtitle": getTranslatedString ("Please check your configuration of time windows with respect to the following sensors to have at least 3 days of measurements: <br/>", lang) + "<br/>".join (emptyTracks),
                    "isError": True
            })
        msExtrapolation['children'].append ({
            "type": 'lineChart',
            "xAxisType": 'time',
            "lines":msExtrapolationLinesNoWeekly
        })
    else:
        msExtrapolation['children'].append ({
                    "type": 'text',
                    "title": getTranslatedString ('No data found for extrapolation without weekly patterns', lang),
                    "subtitle": getTranslatedString ("Please check your configuration of sensors / time windows", lang),
                    "isError": True
            })
    respContent.append ( msExtrapolation)
    if len(noDataWithBaseTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data matching the base sensor in the specified time window', lang),
                        "subtitle": getTranslatedString ("For the following sensors the available data doesn't overlap with the base sensor availability: <br/>", lang) + "<br/>".join (noDataWithBaseTracks),
                        "isError": True
                })
    if len(noDataTracks) > 0:
        respContent.insert (0, {
                        "type": 'text',
                        "title": getTranslatedString ('No data in the specified time window', lang),
                        "subtitle": getTranslatedString ('Please check your time windows configuration for the following sensors: <br/>', lang) + "<br/>".join (noDataTracks),
                        "isError": True
                })
    return respContent

# the routine to verify that timePeriods configuration is correct (by itself) and then fill in the analysis outcome depending on the viewType
def fillSensorTracks (cTs, timePeriods, viewType, withSensorRefs, basePopulationSensorRef, lang):
    for ic, tp in enumerate(timePeriods):
        tpFrom, tpTo = getFromToFromTimePeriod (tp)
        if not tpFrom:
            return [{
                "type": 'text',
                "title": getTranslatedString ('Incorrect configuration for time window', lang) + str(ic + 1),
                "subtitle": getTranslatedString ("Starting date is not valid", lang),
                "isError": True
            }]
        if not tpTo:
            return [{
                "type": 'text',
                "title": getTranslatedString ('Incorrect configuration for time window', lang) + str(ic + 1),
                "subtitle": getTranslatedString ("End date is not valid", lang),
                "isError": True
            }]
        if tpTo < tpFrom:
            return [{
                "type": 'text',
                "title": getTranslatedString ('Incorrect configuration for time window', lang) + str(ic + 1),
                "subtitle": getTranslatedString ("Time window ends before its start. Please correct", lang),
                "isError": True
            }]
    result = []
    if viewType.lower() == 'summary':
        try:
            result += getSummaryView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
        try:
            result += getDataQualityView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'sensors split':
        try:
            result += getSplitView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'daily profiles':
        try:
            result += getDailyProfilesView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'trend analysis':
        try:
            result += getTrendView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'difference on a daily level':
        try:
            result += getDailyLevelDifferenceView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'single track extrapolation':
        try:
            result += getSSExtrapolationView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    if viewType.lower() == 'multiple tracks extrapolation':
        try:
            result += getMSExtrapolationView (cTs, timePeriods, withSensorRefs, basePopulationSensorRef, lang)
        except:
            result += [{
                "type": 'text',
                "title": getTranslatedString ('Fatal error occured', lang),
                "subtitle":  getTranslatedString ('Please notify your IT team about the accident and how have you reached it', lang),
                "isError": True
            }]
            print (traceback.format_exc())
    return result