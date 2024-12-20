def get_airport_detail(airport_iri):
    airport_iri = "http://world-airports-kg.up.railway.app/data/" + airport_iri
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>

        SELECT ?airportName ?countryIRI ?airportType ?latitudeDeg ?longitudeDeg ?elevationFt ?hasScheduledService 
            ?gpsCode ?airportLocalCode ?airportId ?municipality ?regionName ?countryName ?navAidName ?airportIATA
        (GROUP_CONCAT(CONCAT(
           "", IF(BOUND(?runwayLengthInFt), str(?runwayLengthInFt), "-"), 
           " ", IF(BOUND(?runwayWidthInFt), str(?runwayWidthInFt), "-"), 
           " ", IF(BOUND(?runwaySurfaceType), str(?runwaySurfaceType), "-"), 
           " ", IF(BOUND(?runwayIsLighted), str(?runwayIsLighted), "-"), 
           " ", IF(BOUND(?runwayIsClosed), str(?runwayIsClosed), "-"),
           " ", IF(BOUND(?runwayLowerIdent), str(?runwayLowerIdent), "-")
           ); separator = ";") AS ?runways)
        WHERE {{
            <{airport_iri}> rdfs:label ?airportName.
            
            <{airport_iri}> v:region ?regionNode;
                    v:airportType ?airportType;
                    v:latitudeDeg ?latitudeDeg;
                    v:longitudeDeg ?longitudeDeg;
                    v:hasScheduledService ?hasScheduledService;
                    v:airportId ?airportId.

            OPTIONAL {{ <{airport_iri}> v:iataCode ?airportIATA. }}
            OPTIONAL {{ <{airport_iri}> v:elevationFt ?elevationFt. }}
            OPTIONAL {{ <{airport_iri}> v:municipality ?municipality. }}
            OPTIONAL {{ <{airport_iri}> v:gpsCode ?gpsCode. }}
            OPTIONAL {{ <{airport_iri}> v:airportLocalCode ?airportLocalCode. }}
            OPTIONAL {{ 
                <{airport_iri}> v:runways ?runwaysNode. 
                OPTIONAL {{
                ?runwaysNode v:lengthFt ?runwayLengthInFt;
                            v:widthFt ?runwayWidthInFt;
                            v:surfaceType ?runwaySurfaceType;
                            v:isLighted ?runwayIsLighted;
                            v:leIdent ?runwayLeIdent;
                            v:isClosed ?runwayIsClosed;
                            v:leIdent ?runwayLowerIdent.
                }}
            }}
            
            ?regionNode rdfs:label ?regionName.
            OPTIONAL {{ 
                ?regionNode v:countryCode ?countryNode. 
                ?countryNode v:country ?countryIRI.
                ?countryIRI rdfs:label ?countryName.
            }}
            
            OPTIONAL {{
                ?navAid v:associatedAirport <{airport_iri}>;
                rdfs:label ?navAidName.
            }}
        }}
        GROUP BY ?airportName ?countryIRI ?regionName ?countryName ?airportType ?latitudeDeg ?longitudeDeg 
                ?elevationFt ?hasScheduledService ?gpsCode ?airportLocalCode ?airportId ?municipality ?navAidName ?airportIATA
        """

def get_navaids(airport_iri):
    airport_iri = "http://world-airports-kg.up.railway.app/data/" + airport_iri
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>

        SELECT 
        (GROUP_CONCAT(CONCAT(
           "", IF(BOUND(?navName), str(?navName), "-"), 
           "%", IF(BOUND(?navType), str(?navType), "-"), 
           "%", IF(BOUND(?navFreq), str(?navFreq), "-"), 
           "%", IF(BOUND(?navLatDeg), str(?navLatDeg), "-"), 
           "%", IF(BOUND(?navLongDeg), str(?navLongDeg), "-"),
           "%", IF(BOUND(?navElevationFt), str(?navElevationFt), "-"),
           "%", IF(BOUND(?countryIRI), str(?countryIRI), "-"),
           "%", IF(BOUND(?countryName), str(?countryName), "-"), 
           "%", IF(BOUND(?navMagDeg), str(?navMagDeg), "-"),
           "%", IF(BOUND(?navUsageType), str(?navUsageType), "-"),
           "%", IF(BOUND(?navPowerUsage), str(?navPowerUsage), "-"),
           "%", IF(BOUND(?navId), str(?navId), "-")
           ); separator = ";") AS ?navaids)
        WHERE {{
            
            OPTIONAL {{
                ?navAid v:associatedAirport <{airport_iri}>;
                    rdfs:label ?navName;
                    v:navaidType ?navType;
                    v:frequencyKhz ?navFreq;
                    v:latitudeDeg ?navLatDeg;
                    v:longitudeDeg ?navLongDeg;
                    v:elevationFt ?navElevationFt;
                    v:countryCode ?navCountryCode;
                    v:magneticVariationDeg ?navMagDeg;
                    v:usageType ?navUsageType;
                    v:powerUsage ?navPowerUsage;
                    v:navaidId ?navId .

                OPTIONAL {{
                    ?navCountryCode v:country ?countryIRI.
                    ?countryIRI rdfs:label ?countryName.
                }}
            }}
        }}"""
