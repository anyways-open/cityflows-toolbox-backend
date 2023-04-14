from django.contrib import admin
import app.models

admin.site.register(app.models.Modality)
admin.site.register(app.models.SensorType)

class SensorAdmin(admin.ModelAdmin):
    list_display = ('ref', 'hasReverse')
    
admin.site.register(app.models.Sensor, SensorAdmin)

class SensorTrackAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'isReverseChannel', 'modality')
    
admin.site.register(app.models.SensorTrack, SensorTrackAdmin)
	
class HMeasurementAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'date', 'hour', 'count')

admin.site.register(app.models.HMeasurement, HMeasurementAdmin)

class DMeasurementAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'date', 'count', 'count_sum')

admin.site.register(app.models.DMeasurement, DMeasurementAdmin)

admin.site.register(app.models.QualityValidationTest)

class QualityValidationResultAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'date', 'test', 'passed')

admin.site.register(app.models.QualityValidationResult, QualityValidationResultAdmin)
