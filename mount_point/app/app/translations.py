globalTranslationDic = {}

# based on the EN string used in the interface, get the translated one
# if translation is missing - falls back to the EN one
# if EN string needs to be changed - probably easier to define it in globalTranslationDic['en'] with the previous string as a key; then no need to find back the usage in the code
def getTranslatedString (enString, lang):
    if (lang in globalTranslationDic) and (enString in globalTranslationDic[lang]):
        return globalTranslationDic[lang][enString]
    else:
        if lang != 'en':
            print ("Missing " + lang + " translation for:" + enString)
        return enString

# definition of translations for NL
globalTranslationDic['nl'] = {
    'No sensor tracks selected':'Geen sensorsporen geselecteerd',
    'Please select the desired modalities for each sensor in the left menu':'Selecteer de gewenste modaliteiten voor elke sensor in het linkermenu',
    'No time windows configured':'Geen tijdvensters geconfigureerd',
    'Please create and configure at least one time window in the left menu':'Maak en configureer ten minste één tijdvenster in het linkermenu',
    'Total daily counts':'Totale dagelijkse tellingen',
    " (divided by the corresponding count of your selected base sensor)":"(gedeeld door het overeenkomstige telling van uw geselecteerde basissensor)",
    'The following graph is the raw dataset we are working with.':'De volgende grafiek is de onbewerkte dataset waarmee we werken.',
    'Statistics':'Statistieken',
    'Here you can find some pre-calculated statistics for a quick overview.':'Hier vindt u enkele voorberekende statistieken voor een snel overzicht.',
    "Percentile ":"Percentiel ",
    'Standard deviation':'Standaardafwijking',
'The split of counts between different sensor-modalities combinations':'De verdeling van tellingen tussen verschillende combinaties van sensor-modaliteiten',
'''Here we look at each day and the counts for sensor-modalities combinations available at that day. For each of the combination we show the percentage of the total count it represents.<br/>Here are some use cases for this view:<br/> - Getting the modal split: if you select a single sensor with different modalities available, the graph will directly show you the modal split<br/> - Comparing pairs of sensors: if you have a pair of nearby sensors, measuring the same modality, selecting those permits you to directly see and quantify how much of the data one sensor sees compared to the other. In an ideal situation and for the sensors located at the same place you should have a straight line at 50%.''':'''Hier kijken we naar de tellingen van sensor-modaliteitencombinaties voor elke beschikbare dag. Voor elk van de combinaties tonen we het percentage van het totale aantal dat het vertegenwoordigt.<br/>Hier zijn enkele toepassingen van deze visualisatie:<br/> - De modale verdeling verkrijgen: als u een enkele sensor selecteert met verschillende beschikbare modaliteiten, toont de grafiek u direct de modale split<br/> - Vergelijking van paren sensoren: als u een paar sensoren in de buurt heeft die dezelfde modaliteit meten, kan u deze selecteren zodat u direct ziet hoeveel één sensor telt in vergelijking met de ander. In een ideale situatie en voor de sensoren op dezelfde plaats zou je een rechte lijn moeten hebben op 50%.''',
'At least 2 sensors or modalities are needed':'Er zijn minimaal 2 sensoren of modaliteiten nodig',
'As here we want to see the percentage each sensor-modality combination counts, please select at least 2 of them in the left menu':'Aangezien we hier het percentage dat elke sensor-modaliteitscombinatie telt willen zien, selecteer er minimaal 2 in het linkermenu',
'How stably the sensors are working?':'Hoe stabiel werken de sensoren?',
'''We work with different sensors and by construction they can have different properties: for example some can only work during the daylight while others are well working during the night as well. No matter how reliable is the sensor, it can also have some issues, preventing it from the normal functioning.<br/>
                       In order to see how reliable the data we are working with is, for each sensor we look at the number of hourly counts it is generating. Our goal is to have it stable in time (no anomalies). To automate this process, we perform the following checks: <br/>
                       - MinThreshold <span class="questionMark">?<div class="hint">A basic test, verifying that we have at least 3 counts per day</div></span><br/>
                       - PerformanceThreshold <span class="questionMark">?<div class="hint">Only used for sensors having at least 15 days of measurements. Here we are working with a dynamical system, looking at the number of measurements itself, but also at different percentiles of the rolling windows around the date. And we are checking some rules based on these values. For example: if the number of measurements at a particular date is higher than 85% of measurements in the interval [date - 15 days; date + 15 days], that is a valid point, etc.</div></span><br/>
                       - DBSCAN <span class="questionMark">?<div class="hint">The idea here is to look at all the historical data, see what values (numbers of measurements) were observed and create clusters from them (connect the values which are close, in our case differing by one from each other) and check the cluster size (number of days, falling in each cluster). We are using a machine learning algorithm for that, which explains the name <a target="_blank" href="https://en.wikipedia.org/wiki/DBSCAN">DBSCAN</a></div></span><br/>
                       - AllTests is valid when all of the above tests are valid<br/>
                       On the graph below, you can find the number of hourly counts at each day. Color of the point represents the number of succeeded tests and if you hover on top of it, you can see the details.<br/>
                       <b>You can filter out the days, not passing some of the tests in the time-window configuration on the left.</b><br/>
                       That will influence all the graphs we are working with. If you want to see exactly, how it impacts you can create a time window with and without data quality tests filtering to see its impact on the findings.
                       ''':
                       '''We werken met verschillende sensoren en door constructie kunnen ze verschillende eigenschappen hebben: sommige kunnen bijvoorbeeld alleen overdag werken terwijl andere ook 's nachts goed werken. Hoe betrouwbaar de sensor ook is, hij kan ook problemen hebben waardoor hij niet normaal functioneert.<br/>
                        Om te zien hoe betrouwbaar de data is waarmee we werken, kijken we per sensor naar het aantal uur dat deze tellingen genereert. Ons doel is om het in de tijd stabiel te zijn (geen afwijkingen). Om dit proces te automatiseren voeren we de volgende controles uit: <br/>
                        - MinThreshold <span class="questionMark">?<div class="hint">Een basistest, die verifieert dat we ten minste 3 tellingen per dag hebben</div></span><br/>
                        - PrestatieThreshold <span class="questionMark">?<div class="hint">Alleen gebruikt voor sensoren met ten minste 15 dagen aan metingen. Hier werken we met een dynamisch systeem. Er wordt gekeken naar het aantal metingen zelf en ook naar verschillende percentielen van de rollende vensters rond de datum. En we controleren enkele regels op basis van deze waarden. Bijvoorbeeld: als het aantal metingen op een bepaalde datum hoger is dan 85% van de metingen in het interval [datum - 15 dagen; datum + 15 dagen], is dat een geldig punt, etc.</div></span><br/>
                        - DBSCAN <span class="questionMark">?<div class="hint">Het idee hier is om naar alle historische gegevens te kijken, te zien welke waarden (aantal metingen) zijn waargenomen en er clusters van te maken (groepeerd de waarden die dicht bij elkaar liggen, in ons geval één van elkaar verschillen) en controleer de clustergrootte (aantal dagen, vallend in elk cluster). We gebruiken daarvoor een machine learning-algoritme, vandaar de naam <a target="_blank" href="https://en.wikipedia.org/wiki/DBSCAN">DBSCAN</a></div></span><br/>
                        - AllTests is geldig als alle bovenstaande tests geldig zijn<br/>
                        Op onderstaande grafiek kan je het aantal uur met tellingen per dag terugvinden. De kleur van het punt staat voor het aantal geslaagde tests en als u er met de muisaanwijzer op staat, kunt u de details zien.<br/>
                        <b>U kunt de dagen waar sommige tests niet gehaald worden eruit wegfilteren in de tijdvensterconfiguratie aan de linkerkant.</b><br/>
                        Dat heeft invloed op alle grafieken waarmee we werken. Als u precies wilt zien welke impact dit heeft, kunt u een tijdvenster maken met en zonder filtering van gegevenskwaliteitstests om de impact ervan op de bevindingen te zien.
                        ''',
    'Total daily counts':'Totale dagelijkse tellingen',
    '''On the graph below you have the counts generated together with the colors and details (when hovering on top) from the previous graph. Thus you can directly see which measures are impacted if you filter them out in the time window configuration on the left of the interface. <br/>You can also create a time window with and without data quality tests filtering to see its impact on the findings.''':'''Op onderstaande grafiek heb je de tellingen gegenereerd samen met de kleuren en details (wanneer je erboven zweeft) uit de vorige grafiek. U kunt dus direct zien welke maatregelen worden beïnvloed als u ze uitfiltert in de tijdvensterconfiguratie aan de linkerkant van de interface. <br/>U kunt ook een tijdvenster maken met en zonder filtering van gegevenskwaliteitstests om de impact ervan op de bevindingen te zien.''',
    'Average counts at an hour':'Gemiddelde telling op een uur',
    'Here for each modality and each time window we calculate the average counts per hour':'Hier berekenen we voor elke modaliteit en elk tijdvenster de gemiddelde tellingen per uur',
    " and divide them by the corresponding count of your selected base sensor":" en deel ze door de overeenkomstige telling van uw geselecteerde basissensor",
    '. Hover at the point to see the number of days, which were available for the configured time window.':'. Plaats de muisaanwijzer op het punt om het aantal dagen te zien dat beschikbaar was voor het geconfigureerde tijdvenster.',
'No data matching the base sensor in the specified time window':'Geen gegevens die overeenkomen met de basissensor in het opgegeven tijdvenster',
"For the following sensors the available data doesn't overlap with the base sensor availability: <br/>":"Voor de volgende sensoren overlappen de beschikbare gegevens niet met de beschikbaarheid van de basissensor: <br/>",
'No data in the specified time window':'Geen data in het opgegeven tijdvenster',
'Please check your time windows configuration for the following sensors: <br/>':'Controleer uw tijdvensterconfiguratie voor de volgende sensoren: <br/>',
    'Per hour information':'Informatie per uur',
    'Select the hour you are interested in to get more detailed information about it.':'Selecteer het uur waarin u geïnteresseerd bent om er meer gedetailleerde informatie over te krijgen.',
    'Temporal evolution':'Evolutie in de tijd',
    "Here you see how the total count":"Hier zie je hoe de telling",
    " during the selected hour changed for different days":"tijdens het geselecteerde uur wijzigde voor verschillende dagen",
    'Analysis of the data between {h}:00 and {hp1}:00':'Analyse van de gegevens tussen {h}:00 en {hp1}:00',
' for this hour':'voor dit uur',    
'Please add more time windows for comparative analysis':'Voeg meer tijdvensters toe voor vergelijkende analyse',
"If you configure at least 2 time windows at the left panel, we can check how the signal from sensors compares between them":"Als u in het linkerpaneel minimaal 2 tijdvensters configureert, kunnen we controleren hoe het signaal van de sensoren zich verhoudt",
    'Sensors with significant difference':'Sensoren met aanzienlijk verschil',
    'For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives small p-values (below {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can confidently say that the signals observed are significantly different.':'Voor de sensoren hieronder geeft de Kolmogorov-Smirnov-test<a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> voor significant verschillende verdelingen kleine p-waarden (onder {pThr}) <span class="questionMark">?<div class="hint">De test die we gebruiken, beantwoordt de vraag "Wat is de kans dat de 2 datasets die we hebben uit dezelfde distributie komen?". De p-waarde vertegenwoordigt deze kans. Dus als deze kleiner is dan 0,05, kunnen we met een betrouwbaarheidsniveau van 95% zeggen dat het fout is en dat de datasets afkomstig zijn van verschillende distributies.</div></span>. Dit betekent dat we met een gerust hart kunnen zeggen dat de waargenomen signalen significant verschillen.',
    'Sensor':'Sensor',
    'Time window':'Tijdsvenster',
    'mean':'gemiddelde',
    'Sensors without significant difference':'Sensoren zonder significant verschil',
    '''For the sensors below the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for significantly different distributions gives big p-values (above {pThr}) <span class="questionMark">?<div class="hint">The test we are using is answering to the question "What is the probability that the 2 datasets we have are coming from the same distribution?". The p-value represents this probability. Thus, when it is smaller than 0.05, with the confidence level of 95% we can say it is wrong and the datasets are coming from different distributions.</div></span>. This means that we can NOT confidently say that the signals observed are significantly different.''':
        '''Voor de sensoren hieronder levert de Kolmogorov-Smirnov-test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> voor significant verschillende verdelingen grote p-waarden op (boven {pThr}) <span class="questionMark">?<div class="hint">De test die we gebruiken, beantwoordt de vraag "Wat is de kans dat de 2 datasets die we hebben uit dezelfde distributie komen?". De p-waarde vertegenwoordigt deze kans. Dus als het kleiner is dan 0,05, kunnen we met een betrouwbaarheidsniveau van 95% zeggen dat het fout is en dat de datasets afkomstig zijn van verschillende distributies.</div></span>. Dit betekent dat we NIET met zekerheid kunnen zeggen dat de waargenomen signalen significant verschillen.''',
    'Map of differences':'Kaart van verschillen',
'''Our goal here is to compare how the traffic has evolved between selected time windows.<br/>
                                                            To do so, we perform the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for each sensor track (separately for each modality / direction). <br/>
                                                            Colors of the sensors represent the outcomes:<br/>
                                                            - <span style="color:#ff0000">Red</span> means that for the majority of modality/direction pairs the traffic became <b>more intense</b><br/>
                                                            - <span style="color:#00ff00">Green</span> means that for the majority of modality/direction pairs the traffic became <b>less intense</b><br/>
                                                            - <span style="color:#aaaaff">Purple</span> means that no statistically significant difference is observed or there is a balance between different modality/direction pairs<br/>
                                                            - <span style="color:#0000ff">Blue</span> means there is not enough data to make the comparative analysis<br/>
                                                            You can always hover on top of the sensor for more details''':
                                                            '''Ons doel hier is om te vergelijken hoe het verkeer is geëvolueerd tussen geselecteerde tijdvensters.<br/>
                                                             Om dit te doen, voeren we de Kolmogorov-Smirnov-test uit <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark"> ?</span></a> voor elk sensorspoor (apart voor elke modaliteit/richting). <br/>
                                                             Kleuren van de sensoren vertegenwoordigen de uitkomsten:<br/>
                                                             - <span style="color:#ff0000">Rood</span> betekent dat voor de meeste modaliteit/richting-paren het verkeer <b>intensiever</b><br/> werd
                                                             - <span style="color:#00ff00">Groen</span> betekent dat voor de meeste modaliteit/richting-paren het verkeer <b>minder intens</b><br/> werd
                                                             - <span style="color:#aaaaff">Paars</span> betekent dat er geen statistisch significant verschil wordt waargenomen of dat er een balans is tussen verschillende modaliteit/richting-paren<br/>
                                                             - <span style="color:#0000ff">Blauw</span> betekent dat er onvoldoende gegevens zijn om de vergelijkende analyse te maken<br/>
                                                             Je kunt altijd boven op de sensor zweven voor meer details''',
    'Issue found':'Probleem gevonden',
    'Some datasets have less than 14 daily measures, which are needed to make the temporal decomposition and they are thus removed':'Sommige datasets hebben minder dan 14 dagen metingen die nodig zijn om de ontleding in de tijd uit te voeren en worden daarom verwijderd',
    '''The following graph is the raw dataset we are working with. <br/>
                            From it using a one-dimensional convolution <a target="_blank" href="https://en.wikipedia.org/wiki/Kernel_(image_processing)"><span class="questionMark">?</span></a> we are extracting the trend component of the signal. <br/>
                            When the trend is deducted from the signal, we find a weekly periodical component (weekly patterns) and the remaining part is called a residual.<br/>
                            You can see all these components in the next graphs.''':
        '''De volgende grafiek is de onbewerkte dataset waarmee we werken.<br/>
                            Hieruit halen we met behulp van een eendimensionale convolutie <a target="_blank" href="https://en.wikipedia.org/wiki/Kernel_(image_processing)"><span class="questionMark">?</span></a>  de trendcomponent uit het signaal.<br/>
                            Wanneer de trend van het signaal wordt afgetrokken, vinden we een wekelijks periodieke component (wekelijkse patronen) en het resterende deel wordt een residu genoemd.<br/>
                            U kunt al deze componenten in de volgende grafieken zien.''',
    'Datasets have less than 14 daily measures, which are needed to make the temporal decomposition and thus are not shown.':'Datasets hebben minder dan 14 dagelijkse metingen, die nodig zijn om de ontleding in de tijd te maken en worden daarom niet getoond.',
'''From raw data using a one-dimensional convolution <a target="_blank" href="https://en.wikipedia.org/wiki/Kernel_(image_processing)"><span class="questionMark">?</span></a> we are extracting the trend component of the signal. <br/>
                            When the trend is deducted from the signal, we find a weekly periodical component (weekly patterns) and the remaining part is called a residual.<br/>
                            You can see all these components in the next graphs.<br/>
                            <b>Please consider external effects before drawing conclusions: for example for some sensors the decrease/increase in the trend can be related with the meteo conditions or the daylight duration''':
                            '''Van onbewerkte gegevens wordt met behulp van een eendimensionale convolutie <a target="_blank" href="https://en.wikipedia.org/wiki/Kernel_(image_processing)"><span class="questionMark">?</span></a> de trendcomponent uit het signaal gehaald. <br/>
                             Wanneer de trend van het signaal wordt afgetrokken, vinden we een wekelijks periodieke component (wekelijkse patronen) en het resterende deel wordt een residu genoemd.<br/>
                             Je kunt al deze componenten zien in de volgende grafieken.<br/>
                             <b>Overweeg externe effecten voordat u conclusies trekt: voor sommige sensoren kan bijvoorbeeld de afname/stijging van de trend verband houden met de weersomstandigheden of de daglichtduur''',
'The following datasets have less than 14 daily measures, which are required to make the temporal decomposition and they are thus removed: <br/>':'De volgende datasets hebben minder dan 14 dagelijkse metingen, die nodig zijn om de ontleding in de tijd uit te voeren en worden daarom verwijderd: <br/>',
'Datasets have less than 14 daily measures, which are required to make the temporal decomposition and thus are not shown.':'Datasets hebben minder dan 14 dagelijkse metingen, die nodig zijn om de ontleding in de tijd te maken en worden daarom niet getoond.',
'No data found, please check the modalities selection and the time windows configuration':'Geen gegevens gevonden, controleer de modaliteitenselectie en de tijdvensterconfiguratie',
'''Here we verify if the behaviour for each sensor track inside one time window is similar to the other time window.
                                                That is done on the total daily counts.<br/>
                                                Usually it makes sense to configure a short time window and a long one and to see how representable the short one is.<br/>
                                                If one time window is inside the other one, keep an eye on p-values more closely: even a bit higher p-values can represent a significant difference as we are including the overlapping counts in both datasets.''':
                                                '''Hier controleren we of het gedrag voor elke sensorspoor binnen het ene tijdvenster vergelijkbaar is met het andere tijdvenster.
                                                 Dat gebeurt op de totale dagelijkse tellingen.<br/>
                                                 Gewoonlijk is het zinvol om een kort en een lang tijdsvenster te configureren en te kijken hoe representatief het korte tijdsbestek is.<br/>
                                                 Als het ene tijdvenster binnen het andere ligt, houd dan de p-waarden beter in de gaten: zelfs een iets hogere p-waarde kan een significant verschil vertegenwoordigen, aangezien we de overlappende tellingen in beide datasets opnemen.''',
'Please configure exactly 2 time windows for this type of analysis':'Configureer a.u.b. exact 2 tijdvensters voor dit type analyse',
'''Our goal here is to compare how the traffic has evolved between selected time windows.<br/>
                                                            To do so, we perform the Kolmogorov-Smirnov test <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark">?</span></a> for each sensor track (separately for each modality / direction). <br/>
                                                            Colors of the sensors represent the outcomes:<br/>
                                                            - <span style="color:#ff0000">Red</span> means that for the majority of modality/direction pairs the traffic became <b>more intense</b><br/>
                                                            - <span style="color:#00ff00">Green</span> means that for the majority of modality/direction pairs the traffic became <b>less intense</b><br/>
                                                            - <span style="color:#aaaaff">Purple</span> means that no statistically significant difference is observed or there is a balance between different modality/direction pairs<br/>
                                                            - <span style="color:#0000ff">Blue</span> means there is not enough data to make the comparative analysis<br/>
                                                            You can always hover on top of the sensor for more details''':
                                                            '''Ons doel hier is om te vergelijken hoe het verkeer is geëvolueerd tussen geselecteerde tijdvensters.<br/>
                                                             Om dit te doen, voeren we de Kolmogorov-Smirnov-test uit <a target="_blank" href="https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"><span class="questionMark"> ?</span></a> voor elk sensorspoor (apart voor elke modaliteit/richting). <br/>
                                                             Kleuren van de sensoren vertegenwoordigen de uitkomsten:<br/>
                                                             - <span style="color:#ff0000">Rood</span> betekent dat voor de meeste modaliteit/richting-paren het verkeer <b>intensiever</b><br/> werd
                                                             - <span style="color:#00ff00">Groen</span> betekent dat voor de meeste modaliteit/richting-paren het verkeer <b>minder intens</b><br/> werd
                                                             - <span style="color:#aaaaff">Paars</span> betekent dat er geen statistisch significant verschil wordt waargenomen of dat er een balans is tussen verschillende modaliteit/richting-paren<br/>
                                                             - <span style="color:#0000ff">Blauw</span> betekent dat er onvoldoende gegevens zijn om de vergelijkende analyse te maken<br/>
                                                             Je kunt altijd boven op de sensor zweven voor meer details''',
'Incorrect time window configuration':'Onjuiste tijdvensterconfiguratie',
"Time window 1 ends before its start. Please correct":"Tijdvenster 1 eindigt voor de start. Gelieve te corrigeren",
"Time window 2 ends before its start. Please correct":"Tijdvenster 2 eindigt voor de start. Gelieve te corrigeren",
'''Here we use the information from the time window 1 to extrapolate the signal to the time window 2. <br/>
                                                Each sensor track is treated separately.<br/>
                                                If there is any data available for time window 2 it is also shown for comparison.
                                                Extrapolation itself is done using the SARIMAX methodology <span class="questionMark">?<div class="hint">The method belongs to the <a href="https://en.wikipedia.org/wiki/Autoregressive_integrated_moving_average" target="_blank">Autoregressive integrated moving average</a> family. This method tries to learn how the signal evolves and pays attention to both the seasonality effects (weekly patterns in our case) and the so-called non-stationarity (the fact that average values can evolve in time - have a look at the trend analysis tab). For more details it is better to check the link in this popup</div></span><br/>
                                                <b>This type of extrapolation is only useful for short-term predictions. As it doesn't have any external corrections, long-term extrapolations usually increase or decrease unreasonably</b>''':
                                                '''Hier gebruiken we de informatie uit tijdvenster 1 om het signaal te extrapoleren naar tijdvenster 2. <br/>
                                                 Elke sensortrack wordt afzonderlijk behandeld.<br/>
                                                 Als er gegevens beschikbaar zijn voor tijdvenster 2, worden deze ook ter vergelijking weergegeven.
                                                 De extrapolatie zelf wordt gedaan met behulp van de SARIMAX-methodologie <span class="questionMark">?<div class="hint">De methode behoort tot het <a href="https://en.wikipedia.org/wiki/Autoregressive_integrated_moving_average" doel ="_blank">Autoregressieve geïntegreerde voortschrijdend gemiddelde</a> familie. Deze methode probeert te leren hoe het signaal evolueert en besteedt aandacht aan zowel de seizoenseffecten (wekelijkse patronen in ons geval) als de zogenaamde niet-stationariteit (het feit dat gemiddelde waarden kunnen evolueren in de tijd - kijk eens naar de trendanalyse tabblad). Voor meer details kun je beter de link in deze pop-up bekijken</div></span><br/>
                                                 <b>Dit type extrapolatie is alleen nuttig voor kortetermijnvoorspellingen. Omdat er geen externe correcties zijn, nemen langetermijnextrapolaties gewoonlijk onredelijk toe of af</b>''',
'Not enough data in time window 1':'Te weinig data in tijdvenster 1',
"For the following sensors in the timewindow 1 we have less than 14 days of measurements, which are needed for extrapolation: <br/>":"Voor de volgende sensoren in tijdvenster 1 hebben we minder dan 14 dagen aan metingen, die nodig zijn voor extrapolatie: <br/>",
'Incorrect time windows count':'Onjuiste telling van tijdvensters',
'Insufficient number of sensor tracks selected':'Onvoldoende aantal sensorsporen geselecteerd',
'Please select at least 2 sensor tracks for this type of analysis':'Selecteer ten minste 2 sensorsporen voor dit type analyse',
"We only predict to the future based on historical data, thus time window 2 can't be partially before the time window 1. Please correct":"We voorspellen alleen de toekomst op basis van historische gegevens, dus tijdvenster 2 kan geen deel hebben vóór tijdvenster 1. Gelieve te corrigeren",
'''Here we use the information from the time window 1 to extrapolate the signal to the time window 2. <br/>
                                                Each sensor track is predicted based on the information from other tracks.<br/>
                                                If there is any data available for time window 2 it is also shown for comparison.
                                                Extrapolation itself is done using the SARIMAX methodology with exogeneous factors<span class="questionMark">?<div class="hint">The method belongs to the <a href="https://en.wikipedia.org/wiki/Autoregressive_integrated_moving_average" target="_blank">Autoregressive integrated moving average</a> family. This method tries to learn how the signal evolves and pays attention to both the seasonality effects (weekly patterns in our case) and the so-called non-stationarity (the fact that average values can evolve in time - have a look at the trend analysis tab). For more details it is better to check the link in this popup</div></span>''':
                                                '''Hier gebruiken we de informatie uit tijdvenster 1 om het signaal te extrapoleren naar tijdvenster 2. <br/>
                                                 Elke sensortrack wordt voorspeld op basis van de informatie van andere tracks.<br/>
                                                 Als er gegevens beschikbaar zijn voor tijdvenster 2, worden deze ook ter vergelijking weergegeven.
                                                 Extrapolatie zelf wordt gedaan met behulp van de SARIMAX-methodologie met exogene factoren<span class="questionMark">?<div class="hint">De methode behoort tot de <a href="https://en.wikipedia.org/wiki/ Autoregressive_integrated_moving_average" target="_blank">Autoregressieve geïntegreerde voortschrijdend gemiddelde</a> familie. Deze methode probeert te leren hoe het signaal evolueert en besteedt aandacht aan zowel de seizoenseffecten (wekelijkse patronen in ons geval) als de zogenaamde niet-stationariteit (het feit dat gemiddelde waarden kunnen evolueren in de tijd - kijk eens naar de trendanalyse tabblad). Voor meer details kun je beter de link in deze pop-up bekijken</div></span>''',
'With weekly patterns':'Met wekelijkse patronen',
"For the following sensors in the timewindow 1 we have less than 14 days of measurements, which are needed for this extrapolation: <br/>":"Voor de volgende sensoren in tijdvenster 1 hebben we minder dan 14 dagen aan metingen, die nodig zijn voor deze extrapolatie: <br/>",
'Not enough data in time window 1 for the extrapolation with weekly patterns':'Te weinig data in tijdvenster 1 voor extrapolatie met weekpatronen',
"None of the sensors in the time window 1 have at least 14 days of measurements, which are needed for this extrapolation, so this part is removed":"Geen van de sensoren in tijdvenster 1 heeft minimaal 14 dagen aan metingen, die nodig zijn voor deze extrapolatie, dus dit deel is verwijderd",
'Without weekly patterns':'Zonder weekpatronen',
'''Here we don't focus on the identification of weekly patterns. That can generate weaker predictions on the signals having a long time frame available, but the advantage is that we can also focus on the signals only available for a few days.<br/>If no sensor has observations anymore, the signal will converge to a horizontal line''':'''Hier richten we ons niet op het identificeren van wekelijkse patronen. Dat kan zwakkere voorspellingen opleveren voor de signalen die een lange tijd beschikbaar zijn, maar het voordeel is dat we ons ook kunnen concentreren op de signalen die slechts enkele dagen beschikbaar zijn.<br/>Als er geen sensor meer waarnemingen heeft, zal het signaal convergeren naar een horizontale lijn''',
'Some sensors have not enough data in time window 1':'Sommige sensoren hebben onvoldoende data in tijdvenster 1',
"Please check your configuration of time windows with respect to the following sensors to have at least 3 days of measurements: <br/>":"Controleer uw configuratie van tijdvensters met betrekking tot de volgende sensoren om minimaal 3 dagen metingen te hebben: <br/>",
'No data found for extrapolation without weekly patterns':'Geen data gevonden voor extrapolatie zonder weekpatronen',
"Please check your configuration of sensors / time windows":"Controleer uw configuratie van sensoren / tijdvensters",
'Incorrect configuration for time window':'Onjuiste configuratie voor tijdvenster',
"Starting date is not valid":"Startdatum is niet geldig",
"End date is not valid":"Einddatum is niet geldig",
"Time window ends before its start. Please correct":"Tijdvenster eindigt voordat het begint. Gelieve te corrigeren",
'Fatal error occured':'Er is een fatale fout opgetreden',
'Please notify your IT team about the accident and how have you reached it':'Informeer uw IT-team over het ongeval en hoe u het heeft bereikt'
}