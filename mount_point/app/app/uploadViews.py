from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from datetime import datetime
from django.core.files.storage import FileSystemStorage

from io import StringIO
from io import BytesIO

import os
import pickle
import json
import traceback
import os
import csv

import app.models

# parsing and handling the data from the API push request. 
# use @protected_resource() decorator to enforce the OAuth verification
@csrf_exempt
def pushData (request):
    try:
        payload = json.loads (request.body)
        for cSensor in payload['sensors']:
            cS = app.models.Sensor.objects.filter (ref=cSensor['ref']).first()
            if cS:
                cS.location = json.dumps (cSensor['location'])
                cS.sensorType = app.models.SensorType.objects.get (name=cSensor['sensorType'])
                cS.meta = json.dumps (cSensor['meta'])
                cS.save ()
            else:
                sensorType = app.models.SensorType.objects.filter (name=cSensor['sensorType']).first ()
                if not sensorType:
                    sensorType = app.models.SensorType.objects.create (name=cSensor['sensorType'])
                cS = app.models.Sensor.objects.create (ref=cSensor['ref'], location=json.dumps (cSensor['location']), hasReverse=False,  meta=json.dumps (cSensor['meta']), sensorType=sensorType)
            modalities = set()
            hadReverse = False
            for track in cSensor['tracks']:
                mod = app.models.Modality.objects.filter (name=track['modality']).first ()
                if not mod:
                    mod = app.models.Modality.objects.create (name=track['modality'])
                modalities.add (mod)
                cTrack = cS.tracks.filter (isReverseChannel=track['isReverse']).filter (modality=mod).first ()
                if not cTrack:
                    cTrack = app.models.SensorTrack.objects.create (sensor=cS, isReverseChannel=track['isReverse'], modality=mod)
                if track['isReverse']:
                    hadReverse = True
                for count in track['counts']:
                    cdate = datetime.strptime (count['date'], "%Y-%m-%d").date()
                    cCount = cTrack.hMeasurements.filter (date=cdate).filter (hour=count['hour']).first()
                    if cCount:
                        cCount.count = count['count']
                        cCount.save()
                    else:
                        app.models.HMeasurement.objects.create (sensor=cTrack, date=cdate, hour=count['hour'], count=count['count'])
                cTrack.exploreDataConsistency()
            cS.hasReverse = hadReverse
            cS.availableModalities.set (modalities)
            cS.save()
    except:
        print (traceback.format_exc())
    return HttpResponse ("Got it")

# CSV upload view and parsing script
# expects the following columns: sensor_type,sensor_ref,modality,is_reverse_channel,date,hour,count,meta
# use @login_required decorator to password protect
def uploadCSV(request):
    if request.method == 'POST' and request.FILES['upload']:
        newData = {}
        sensorType = {}
        sensorLocation = {}
        sensorMeta = {}
        decoded_file = request.FILES['upload'].read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        cnt = 0
        for row in reader:
            ref = row['sensor_ref']
            if ref not in newData:
                newData[ref] = {}
                sensorType[ref] = row['sensor_type']
                sensorMeta[ref] = row['meta']
                sensorLocation[ref] = row['location']
            mod = row['modality']
            if mod not in newData[ref]:
                newData[ref][mod] = {}
            rev = row['is_reverse_channel']
            if rev not in newData[ref][mod]:
                newData[ref][mod][rev] = []
            
            newData[ref][mod][rev].append ((datetime.strptime (row['date'], "%Y-%m-%d").date(), row['hour'], row['count']))
            cnt += 1
        ecnt = 0
        cnt = 0
        for ref in newData:
            cType = app.models.SensorType.objects.filter (name=sensorType[ref]).first()
            if not cType:
                cType = app.models.SensorType.objects.create (name=sensorType[ref])
            cS = app.models.Sensor.objects.filter (ref=ref).first()
            if cS:
                cS.location = sensorLocation[ref]
                cS.sensorType = cType
                cS.meta = sensorMeta[ref]
                cS.save ()
            else:
                cS = app.models.Sensor.objects.create (ref=ref, location=sensorLocation[ref], hasReverse=False, meta=sensorMeta[ref], sensorType=cType)
            for cMod in newData[ref]:
                mod = app.models.Modality.objects.filter (name=cMod).first ()
                if not mod:
                    mod = app.models.Modality.objects.create (name=cMod)
                
                for isRev in newData[ref][cMod]:
                    cTrack = cS.tracks.filter (isReverseChannel=isRev).filter (modality=mod).first ()
                    if not cTrack:
                        cTrack = app.models.SensorTrack.objects.create (sensor=cS, isReverseChannel=isRev, modality=mod)
                    
                    for count in newData[ref][cMod][isRev]:
                        cCount = cTrack.hMeasurements.filter (date=count[0]).filter (hour=count[1]).first()
                        if cCount:
                            cCount.count = count[2]
                            cCount.save()
                            ecnt += 1
                        else:
                            app.models.HMeasurement.objects.create (sensor=cTrack, date=count[0], hour=count[1], count=count[2])
                            cnt += 1
                    cTrack.exploreDataConsistency()
            
            modalities = set()
            hasReverse = False
            for cTrack in cS.tracks.all ():
                modalities.add (cTrack.modality)
                hasReverse = hasReverse or cTrack.isReverseChannel
            cS.hasReverse = hasReverse
            cS.availableModalities.set (modalities)
            cS.save()
        return render(request, 'csvupload.html', {'messages': ['File uploaded successfully']})
    return render(request, 'csvupload.html')

