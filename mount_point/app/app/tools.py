from django.http import HttpResponse
import json

# tiny helpers

def dumper(obj):
    '''dumper: by default to json, if not - to dict'''
    try:
        return obj.toJSON()
    except:
        return obj.__dict__

def jsonResponseFromDic (dic):
    return HttpResponse(json.dumps(dic, default=dumper, indent=2), content_type='application/json')

def getDecodedRequestBody (request):
    if not request.body:
        return request.body
    if ('Content-Encoding' in request.headers) and ('gzip' in request.headers['Content-Encoding']):
        return gzip.decompress(request.body).decode("utf-8")
    return request.body.decode("utf-8")

def formatFloat (val):
    if val >= 0.01:
        return "{:.2f}".format(val)
    return "{:.2e}".format(val)