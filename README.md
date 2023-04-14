# CityFlows Analytical Toolbox backend

In this repository you can find the code of the CityFlows Analytical Toolbox backend. 

The Cityflows toolbox is aiming to help traffic specialists (engineers) mainly working for the public authorities / cities in the context of mobility enhancement and control. At the current stage the main added value is in the simplicity of making relatively complex statistical analysis based on multi-source data. Our persona should be able to not only get some results from the black box but understand (on a desired level) what is happening inside, so that the outcomes can be used with a confidence.

## General toolbox architecture

The mobility data is usually hardly accessible for general public and thus obtained by our final users (cities) on a case-by-case basis from both public and private actors. With that in mind we have opted to a full separation of toolbox instances between different deployments: each client/case deployment is a new one, without mutualization of resources. From one side it creates an entry barrier: there is no always-on platform already running when a new case is started; from the other side we get a full traceability of both data flows and the resources consumed. In order to simplify the above entry barrier, toolbox is deployed as a collection of Docker containers thus heavily limiting the number of installation steps to follow as well as the compatibility with different platforms. 

Taken into account that the toolbox is focusing on a scientific analysis of the data, it was comfortable to make a use of different python libraries available for those purposes. As we were hardly imagining our persona to operate with codes, we were aiming at a user-friendly GUI and to maximize the possible adoption – the web-based application approach was selected. These remarks resulted in the following collection of Docker containers representing the full deployment of the Cityflows toolbox:
-	The backend based on Django framework. A well established and supported by the community framework with an extremely versatile collection of libraries, heavily simplifying the development (see below).
-	The frontend is based on React JS framework, which is one of the top options for frontend development at the moment.
-	After the analysis of the data to be stored / queried for data storage we have opted to PostgreSQL database.

Frontend container

After logging in to the toolbox, the user can interact with two main parts of the frontend:
-	the general map view, which is used for an overview and the selection of the sensors to work with
-	the analysis view: from one side here it is possible to further finetune the selection of sensors (the desired modalities and / or directions) and time windows the user is interested, from the other side in different tabs, the user can see the results of the analysis performed on the data he/she has selected.

The map view is built on top of Leaflet JS map framework and is pretty straightforward. It simply receives the collection of available sensors from the API (formal description in the dedicated section). The analysis view is a bit different. There is a collection of pre-defined building blocks, which are previewed (textual information, different chart types, map visualization, …) and depending on the selection made by the user, which are sent to the backend via an API, the latter one returns which building blocks and with which contents should be shown to the user. So there is a strong bias towards the logic control on the backend side, while the frontend is used solely for the interaction with the user.

Main libraries used in the frontend:
-	React JS – the global framework
-	Leaflet JS – map visualizations
-	Chart JS – visualizations of different charts

The frontend container runs without any persistent storage. 
The following environment variables should be configured at the launch time:
-	`REACT_APP_BACKEND_URL`: full URL (with protocol), where the backend responds
-	`REACT_APP_OAUTH_CLIENT_ID` and `REACT_APP_OAUTH_CLIENT_SECRET`: a pair of id/secret used for authentication purposes (together with the user login/password). Usually a pair of randomly generated strings
-	`REACT_APP_INITIAL_MAP_CONFIG_JSON`: a JSON string, configuring the initial map position in the interface. Example: {"center":[51.003543,3.708080],"zoom":14}
-	`REACT_APP_INITIAL_TIME_WINDOWS`: a JSON string, configuring the initial time windows pre-populated when the user enters to the toolbox. Example: [{"from":"2021-09-01T00:00:00.000Z","to":"2021-11-01T00:00:00.000Z","Monday":true,"Tuesday":true,"Wednesday":true,"Thursday":true,"Friday":true,"Saturday":true,"Sunday":true,"Holiday":true,"Non-holiday":true,"DBSCAN":true,"MinThreshold":true,"PerformanceThreshold":true}]

The webserver started in the container listens to the port 3000. It should be forwarded to external proxy (taking care of https handling).

 
## Database

As mentioned above, we have opted for PostgreSQL database, which is completely controlled from the backend side (including the migrations management).

The toolbox was tested with the version tagged postgres:15.1-alpine, available at the Docker hub.

The path `/var/lib/pgsql/data` should be mounted to a persistent storage.

Environment variable `POSTGRES_PASSWORD` should be set to a randomly generated string, while the POSTGRES_USER variable should be set to “cf”.

 
## Backend container

For obvious reasons in this part most of the logic is contained. The data is managed via a creation of high-level Django models, which are then translated to and managed in the database. Let’s focus first on the structure of models.

## Data Models

The main object of the analysis consists of a collection of measurement (counts) coming from different sensors. As we are working with the traffic data, those counts can be split by transport type (modality) and/or direction. In order to comfortably handle the above-mentioned data, the following model types are created:

-	`Sensor Type` – stores the name of the data provider and used to group together similar sensors. Generated automatically during the data upload (if new)
-	`Modality` – stores the name of the modality and used to classify different types of counts. These are also generated automatically during the data upload (if new). Currently the frontend has pictograms for `Car`, `Bike`, `Pedestrian`, `Background` (total population observed, without modality split). Of course more modalities can be easily added: for example a split to heavy trucks/buses/…
-	`Sensor` – a high level structure directly containing the meta information (unique identifier, location, …) and grouping together the Sensor Tracks
-	`Sensor Track` – a single channel of a sensor counting a fixed modality with optional split in direction: if a sensor counts 2 directions separately for a specific modality, there will be 2 different sensor tracks (one with isReverse = True and one with False) for this modality. Sensor tracks group together the hourly and daily counts.
-	`Hourly Count` – a single measurement for a particular sensor track at a fixed date and hour. Contains the total number of observed instances during this hour.
-	`Daily Count` – a sum of hourly counts for a particular date and a particular sensor track. Used to increase the speed of calculations which don’t need an hourly level of temporal precision.

Here we emphasize the fact that the highest temporal resolution stored in the toolbox is equal to 1 hour. That choice was done as from one side the majority of data sources give only this level of temporal resolution and from the other side, the finer resolution (if available) usually has rather noisy behavior. Having the same time resolution makes things directly comparable among sensors. The step of agglomeration of more fine-resolution signal is a priori the only preprocessing step required before the data is uploaded to the toolbox.

It is totally fine if not all hourly measurements are present. Those can be absent due to various reasons, like technical issues, privacy reasons or functioning type (for example Telraam uses the camera image processing to generate the counts and thus has limited functionality at night due to the visibility issues). To raise the user awareness of such situations, each sensor track goes through a collection of automated tests to detect which days are comparable to a normal behavior of this particular sensor track and which – not. The results of these tests are stored in the Data Quality Test Result models (on a daily level per sensor track and per Quality Test type). These tests are passed at each data upload. There are 2 important remarks to note here:
1.	Data quality is understood here in terms of the coming signal persistence, without focus on the values returned. I.e. if a sensor always gives 8 hourly counts per day, that is considered as a persistent behavior even if on day 1 there were 1000 people observed and on day 2 – 0. The reason of not considering outliers as faulty measurements is that we are potentially interested exactly in those outliers during the analysis (example: an event happening on a particular day). 
2.	With respect to the above-mentioned tests, the missing measurement has a very different meaning of the measurement equal to 0 count. This means that for sure it is bad to artificially add 0 counts instead of missing measurements. In case it is possible to diversify between a missing count and a 0 count for a specific provider, it is always worth the effort.
The user can easily filter out the sensor data not passing some of the tests in the time-window configuration in the frontend. This potentially permits to focus on the most qualitative parts of the available data.

Together with the above-mentioned application specific models, backend also creates more generic models needed for the Django framework itself (mostly related to the users management) or for some of the used libraries (probably the only relevant to note here is the OAuth2 provider configuration).

## API endpoints for Frontend

The first part of the API for frontend contains everything related to the OAuth2 authentication. Here we completely rely on the Django Oauth Toolkit ( https://django-oauth-toolkit.readthedocs.io/ ) without any amendments. Thus for further details on this part it is better to consult the original documentation. We limit here to the following remarks:
-	All the paths are prefixed by `BACKEND_URL/o/`
-	Django Oauth Toolkit is rfc-compliant and there is a possibility to use external token providers. As in the current use cases the technical team and the final users are coming from different organizations it was not worth to use the single-sign-on options, that is why we have kept the user’s management on the Django side.

The “content-related” API is served via a unique URL `BACKEND_URL/api/api` . It expects a BEARER token in the header and a JSON payload in the request body. The return is in the JSON format as well.
As the URL is common for different functions, the obligatory parameter in the the JSON payload is `endpoint`. Below there is a list of valid endpoints and their specifications.

### Sensors Collection endpoint
##### Body params:
```
{
    “endpoint”: “getSensorsCollection”
}
```

##### Expected result:
```
{
    "status":"ok", 
    "sensorCards": ARRAY_OF_AVAILABLE_SENSORS_DETAILS
}
```

For each available sensor the following dictionary is expected:
```
{
            "ref": SENSOR_UNIQUE_REFERENCE,
            "location": GEOJSON_LOCATION_PROPERTIES,
            "modalities": ARRAY_OF_AVAILABLE_MODALITIES_NAMES,
            "hasReverse": BOOLEAN_VALUE_SPECIFYING_IF_TWO_DIRECTIONS_ARE_AVAILABLE,
            "sensorType": { “name” : PROVIDER_NAME },
            "extraFields": { “addressString” : “” }
            "quality": PERCENTAGE_OF_DAYS_PASSING_ALL_TESTS
}
```
extraFields dictionary is optional (subject to availability) and can have different meta information inside. Other fields are obligatory.

##### Example result:
```
{
	"status": "ok",
	"sensorCards": [
{
		"ref": "9000001421",
		"location": {
			"id": "0",
			"type": "Feature",
			"properties": {},
			"geometry": {
				"type": "LineString",
				"coordinates": [
					[3.710991496082532, 50.99672140240988],
					[3.7117315960823807, 50.99699980240989]
				]
			},
			"bbox": [3.710991496082532, 50.99672140240988, 3.7117315960823807, 50.99699980240989]
		},
		"modalities": ["Bike", "Car", "Pedestrian"],
		"hasReverse": true,
		"sensorType": {
			"name": "telraam"
		},
		"extraFields": {},
		"quality": 76.34408602150539
	}]
}
```

### Sensor Card endpoint
##### Body params:
```
{
“endpoint”: “getSensorCard”
“ref”: SENSOR_UNIQUE_REFERENCE
}
```

##### Expected result:
```
{
	"status": "ok",
	"sensor": SENSOR_CARD_AS_IN_SENSORS_COLLECTION
}
```
##### Error result:

Raised if sensor with specified reference was not found
```
{
'status': 'error_occurred', 
'error': 'No sensor found'
}
```

### Sensor Cards endpoint
##### Body params:
```
{
“endpoint”: “getSensorCard”
“refs”: ARRAY_OF_SENSOR_UNIQUE_REFERENCES
}
```

##### Expected result:
```
{
	"status": "ok",
	"sensors": ARRAY_OF_SENSOR_CARDS_AS_IN_SENSORS_COLLECTION
}
```
If some references are not found, they are ignored – no error is raised!


### Main analysis endpoint
Body params (details below):
```
{
“endpoint”: “getMultiSourceTrack”
“viewType”: ONE_OF_THE_AVAILABLE_ANALYSIS_TYPES
“timePeriods”: ARRAY_OF_TIME_WINDOWS_TO_USE_FOR_ANALYSIS
“refModalityReverseCombinations”: CONFIGURATION_OF_SENSOR_TRACKS
“lang”: 2_LOWERCASE_LETTERS_LANGUAGE_CODE_TO_USE_FOR_RESPONSE
“basePopulationSensorRef”: WHICH_SENSOR_TO_USE_AS_BASE
}
```

**viewType:**
Possible analysis types (case insensitive):
-	`“ummary`: general statistics, raw data charts and data persistence analysis
-	`sensors split`: this view aims at comparing different sensor tracks via a visualization of relative values of the total population captured
-	`daily profiles`: a deeper analysis of per hour data and its evolution over time; includes the statistical comparison between time windows on an hourly level
-	`trend analysis`: identification of weekly periodic components and the global trend analysis
-	`difference on a daily level`: statistical comparison of the signal on a daily level
-	`single track extrapolation`: temporal extrapolation of the signal of single tracks
-	`multiple tracks extrapolation`: temporal extrapolation of the signal of single tracks using the information from other tracks
-	`extractRawCSVData`: just filters the data and returns the downloadable CSV file with the selected data
For deeper explanation of different view types we refer to the tool itself and the helpers inside it.

**timePeriods:**
It is possible to submit different number of “time windows” in an array. Each of them is represented by the following dictionary:
```
{
    "from":UNIX_TIME_IN_MS_OR_TEXTUAL_STRING,
    "to": UNIX_TIME_IN_MS_OR_TEXTUAL_STRING,
    "Monday": BOOLEAN_FLAG_SPECIFYING_IF_MONDAYS_ARE_USED,
    "Tuesday": SIMILAR_TO_MONDAY,
    "Wednesday": SIMILAR_TO_MONDAY,
    "Thursday": SIMILAR_TO_MONDAY,
    "Friday": SIMILAR_TO_MONDAY,
    "Saturday": SIMILAR_TO_MONDAY,
    "Sunday": SIMILAR_TO_MONDAY,
    "Holiday": BOOLEAN_FLAG_SPECIFYING_IF_PUBLIC_HOLIDAYS_ARE_USED,
    "Non-holiday": BOOLEAN_FLAG_SPECIFYING_IF_NON_PUBLIC_HOLIDAYS_ARE_USED,
    "DBSCAN": BOOLEAN_FLAG_SPECIFYING_IF_DAYS_NOT_PASSING_THIS_TEST_ARE_USED,
    "MinThreshold": SIMILAR_TO_DBSCAN,
    "PerformanceThreshold": SIMILAR_TO_DBSCAN
}
```
**refModalityReverseCombinations:**
Configuration of sensor tracks is done via a nested dictionary of the following format:
```
{ 
	SENSOR_UNIQUE_REFERENCE: {
		MODALITY_NAME: {
            "false": BOOLEAN_IF_NORMAL_DIRECTION_IS_USED,
            "true": BOOLEAN_IF_REVERSE_DIRECTION_IS_USED
		}
	}
}
```

Some remarks here:
-	The structure is SENSOR_REFERENCE -> MODALITY_NAME -> IS_REVERSE_DIRECTION -> BOOLEAN_VALUE_TO_INCLUDE_OR_NOT
-	IS_REVERSE_DIRECTION key is a string to be compliant with JSON specifications
-	In this dictionary a Boolean flag set to false is equal to the missing key (sensor track is not used).
-	If a sensor doesn’t differentiate 2 directions, then the “false” key should be used

lang:
Currently only “en” and “nl” are supported for the language

**basePopulationSensorRef:**
The total observed population can vary in different time periods, thus for some applications it might be useful to look not at the absolute values, observed by a sensor, but how they evolve compared to some benchmark. If basePopulationSensorRef set to some sensor unique reference, then in the analysis we will divide the observed counts by a total population seen by that sensor at the corresponding day/hour (if available).


##### Body params example:
```
{
 	"endpoint": "getMultiSourceTrack",
    "viewType": "Summary",
        "timePeriods": [
            {
                "from": 1630454400000,
                "to": 1635724800000,
                "Monday": true,
      			"Tuesday": true,
                "Wednesday": true,
                "Thursday": true,
                "Friday": true,
                "Saturday": true,
                "Sunday": true,
                "Holiday": true,
                "Non-holiday": true,
                "DBSCAN": true,
                "MinThreshold": true,
                "PerformanceThreshold": true
    		}
  	],
    "refModalityReverseCombinations": {
        "39472": {
            "Car": {
                "false": true,
                "true": true
                },
                    },
                "9000000131": {
                "Bike": {
                "false": true,
                "true": false
                },
            }
    },
    "basePopulationSensorRef": null,
    "lang": "en"
}
```
##### Expected result:
```
{
	"status": "ok",
	"multiSourceTracks": {
		“contents”: ARRAY_OF_BASE_ITEMS_TO_SHOW_IN_THE_FRONTEND
	}
}
```
Base items have the following general syntax (other fields are necessary depending on the type) and can be combined together:
```
{
	“type”: “text” / ”lineChart” / “scatterChart” / “table” / “map” / “list” / “selectable”
	"title": TITLE_TO_SHOW (optional)
	“subtitle”: SUBTITLE_TO_SHOW (optional)
	“isError”: BOOLEAN_FLAG_TO_RAISE_ATTENTION (optional)
    "collapsed": BOOLEAN_FLAG_IF_SHOWN_COLLAPSED_BY_DEFAULT
}
```

#### lineChart / scatterChart additional parameters:
The parameters in bold are coming from the ChartJS properties and should be checked there in case not self-explanotary ( https://www.chartjs.org/ ):
```
{
    “xAxisType”: “linear” / “time” / …,
    “xAxisStep”: ,
    “yAxisStep”:,
    “yAxisMin”: ,
    “yAxisMax”:,
    “lines”: [
        {
            “data”: LIST_OF_DICTIONARIES_HAVING_X_AND_Y_KEYS_AND_VALUES,
            “showLine”: ,
            “label”: LABEL_OF_THE_LINE_FOR_THE_LEGEND (optional),
            “tooltips”: ARRAY_OF_TOOLTIP_STRINGS_FOR_EACH_POINT_IN_DATA (optional),
            “pointColors”: ARRAY_OF_RGB_COLORS_TO_USE_FOR_NODES (optional),
            “colorCounter”: THE_COUNTER_OF_THE_COLOR_TO_TAKE_FROM_THE_PALLETTE,
            “timePeriodCounter”: WHICH_TIME_WINDOW_IT_RELATES_TO (for styling purposes; starts from 0)
            “fill”: IF_THE_SPACE_TO_A_DIFFERENT_LINE_SHOULD_BE_FILLED_WITH_COLOR (optional)
        },
    …
    ]
}
```

#### table additional parameters:
```
{
	“captions”: ARRAY_OF_STRINGS_FOR_THE_TABLE_HEADER_LINE,
	“lines”: ARRAY_OF_ROWS_EACH_OF_THEM_BEING_AN_ARRAY_OF_STRINGS_FOR_THE_ROW
}
```

#### list additional parameters:
```
{
	“children”: ARRAY_OF_BASE_ITEMS
}
```

#### Selectable (shows a tabular structure) additional parameters:
```
{
	“children”: [
{
			“label”: LABEL_TO_SHOW_ON_THE_CORRESPONDING_TAB_BUTTON,
			“item”: BASE_ITEM_TO_SHOW_IN_TAB 
		},
		…
	]
}
```

#### map additional parameters:
```
{
	“meta”: {
		SHOWING_SENSOR_REFERENCE: {
			“color”: HTML_COLOR_TO_USE_FOR_THIS_SENSOR
			“detailsString”: THE_TEXT_TO_SHOW_IN_THE_HOVER_POPUP,
			“detailsHtmlString”: THE_HTML_CODE_TO_SHOW_IN_THE_HOVER_POPUP
        },
    …
    }
}
```

### Technical views / APIs
`BACKEND_URL/admin/*` and `BACKEND_URL/accounts/*` used for the DJANGO admin panel and authentication routines (see https://docs.djangoproject.com/en/4.1/ for details).

`BACKEND_URL/upload/csv/` and `BACKEND_URL/pushData` are used for data upload (see the corresponding section below).

### External dependencies
The data treatment is articulated around Scikit-Learn ( https://scikit-learn.org/ ) and Statsmodels ( https://www.statsmodels.org/ ) libraries. 
The preprocessing pipelines are using Pandas ( https://pandas.pydata.org/ ). 
To simplify the classification of days (public holidays identification) Holidays ( https://github.com/dr-prodigy/python-holidays ) library is used.
The rest of external dependencies are related to Django framework itself and its optional packages (OAuth2 / CORS / …).

### Container configuration
Django models system automatically manages the translation of the high-level model definition / access to the database tables creation / querying. As those can change in time with the new versions of code developed, the migrations system is put in place, storing the whole history of database scheme modifications and adapting it in case of code changes. These migrations are stored in the raw files on the disk (and not in the database itself). For the external libraries / imported applications, those go together with the library application code and thus coupled with the version control. As the toolbox itself is still in an active phase of development and is responsible for the client data, it is relevant to store the migration files on the persistent storage. Thus the path `/app/app/app/migrations` of the backend container should be mounted to a latter one.

The following environment variables must be set for correct functioning of the container:
-	`internalURLs` – the IP address to which the web server proxy is forwarded to. Can be set to  '*' not to include the extra protection.
-	`apiURL` – the full URL (with protocol) at which the backend is accessed
-	`debugMode` – `0`or `1` to disable/enable the Django embedded debug mode (not secure for production but permits easy error management).
-	`CORSWhiteListed` – frontend full URL (with protocol). Used for CORS protection exception.
-	`dbPass` – the `POSTGRES_PASSWORD` configured for the database container
-	`dbHost` – the name of the database container or the hostname for externally accessible databases

The backend container web-server listens on the port 80. It should be forwarded to external proxy (taking care of https handling).

 
## First launch installation steps

When the collection of toolbox container is launched it is not yet populated with any (including operational) data. The following steps are needed to make the system functional:

1.	Execute the following commands in the backend container:
    a.	`python3 /app/app/manage.py makemigrations app`
    (Creation of the migrations files for the toolbox main application)
    b.	`python3 /app/app/manage.py migrate`
    (Execution of the above created and already available external libraries migrations for the database scheme population)
    c.	`python3 / app/app/manage.py createsuperuser`
    (Creation of the super admin user in an interactive shell)
2.	Navigate to the `BACKEND_URL/o/applications/`, authenticate with the super user credentials and create a new OAUTH2 application with the following parameters:
    a.	Client type – confidential
    b.	Grant type - resource owner password
    c.	Client ID / Client Secret – same as `REACT_APP_OAUTH_CLIENT_ID` / `REACT_APP_OAUTH_CLIENT_SECRET` environment variables set for the frontend container.
3.	(Optional) Navigate to `BACKEND_URL/admin/` -> Users and create additional users who will have access to the toolbox.
4.	Upload the sensors data (see below)

 
## Toolbox data upload options
 
### API upload
The first option to upload the data consists in pushing JSON encoded data directly to the backend endpoint. If BACKEND_URL is the URL, where backend is hosted, then the target endpoint is `BACKEND_URL/pushData`.
 
Currently the data upload is open without any authentication as it is in a write-only mode and thus not involving any privacy issue. Moreover the platforms are not designed for broad audience, thus the risks of random data being pushed are limited. In case needed, the OAUTH2 authentication can be enabled with a single-line decorator in the backend to mimic the protection pipeline used by the frontend.
 
The JSON should be posted in the body of the request and have the format similar to the following:
```
{
    “sensors”: [
        {
            “ref”:”SENSOR_REF”,
            "location": {“type”:”point”,”coords”:[LAT, LON] },
            “sensorType”:”SENSOR_TYPE_STRING”,
            “meta”: { ANY_META_INFORMATION_TO_STORE_IN_THE_BACKEND}, “tracks”:[
                {
                    “modality”: “Car”, 
                    “isReverse”: False, 
                    "counts":[
                        {
                            “date”: String in format %Y-%m-%d", “hour”: HOUR_INTEGER_VALUE, “count”: OBSERVED_COUNT_AT_THAT_HOUR
                        }
                    ]
                }
            ]
        }
    ]
}
```
General comments: 
•	all the arrays can have multiple values.
•	If the data contradicts the data stored in the database, it will be modified
•	Location can have the following types:
•	point: then coords have the lat,lon pair
•	linestring: then coords have a string similar to `'LINESTRING (4.470560418428409 51.01749874553107, 4.470670605706021 51.01738049739185, … )`
•	geojson: then coords have the geojson string.
•	Sensor type is usually a data provider name
•	Meta information is flexible. The only currently used field (optional) is “addressString” to show the human readable address in the interface
•	Modality can be one of `Car`, `Bike`, `Pedestrian`, `Background`
•	isReverse is used to take into account 2 directions of the street.


### CSV upload
The second option to upload the data consists in the upload of the CSV file dumps to the backend endpoint. If BACKEND_URL is the URL, where backend is hosted, then the target url is `BACKEND_URL/upload/csv/`.
 
Currently the data upload is open without any authentication as it is in a write-only mode and thus not involving any privacy issue. Moreover the platforms are not designed for broad audience, thus the risks of random data being pushed are limited. In case needed, the password protection can be enabled with a single-line decorator in the backend.

The csv file lines format should follow the following header:

`sensor_type,sensor_ref,modality,is_reverse_channel,date,hour,count,location,meta`

The field descriptions are exactly the same as for the API upload, just the structure is in the flat file (thus location and meta are duplicated in each sensor count line in order to avoid multi-stage uploads)


