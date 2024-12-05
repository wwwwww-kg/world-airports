from django.shortcuts import render, redirect
from django.urls import reverse
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

from main.query import get_airport_detail, get_navaids

# Setup environment variables
env = environ.Env()
environ.Env.read_env()
local_rdf = env("LOCAL_RDF_HOST")
base_iri = env("BASE_IRI")

def replace_uri_with_iri(uri):
    iri = uri.replace(base_iri + "/data/", "")
    return iri

def create_uri_from_iri(iri):
    uri = "<" + base_iri + "/data/" + iri + ">"
    return uri

# Create your views here.
def index(request):
    ''' Menampilkan halaman utama '''
    query = request.GET.get("q")

    if query != None:
        return redirect(reverse("search") + "?q=" + query)

    context = {
        'page_title': "homepage",
    }
    return render(request, "index.html", context)

def search(request):
    ''' Menampilkan hasil pencarian '''

    query = request.GET.get("q").lower()
    local_data_wrapper = SPARQLWrapper2(local_rdf)

    ## Attempt to get basic airport data via SPARQL with FILTER
    local_data_wrapper.setQuery(f"""                                
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>

    SELECT ?airport_iri ?airport_name ?airport_iata ?region_name ?country_name ?airport_gpscode ?airport_localcode 
    WHERE {{
            ?airport_iri a [rdfs:label "Airport"];
                rdfs:label ?airport_name;
                v:region ?region_node .
            ?region_node rdfs:label ?region_name;
                v:countryCode [v:country [rdfs:label ?country_name]] .
            OPTIONAL {{ ?airport_iri v:iataCode ?airport_iata. }}
            OPTIONAL {{ ?airport_iri v:gpsCode ?airport_gpscode. }}
            OPTIONAL {{ ?airport_iri v:airportLocalCode ?airport_localcode. }}
            FILTER CONTAINS(LCASE(?airport_name), "%s") .
    }} ORDER BY ?airport_name LIMIT 50
    """ % query)

    matching_results = local_data_wrapper.query().bindings
    sorted_results = []
    sorted_similars = []

    if matching_results != []:
        ## Sort results from most relevant
        for entry in matching_results:
            airport_name = entry["airport_name"].value
            entry["airport_iri"].value = replace_uri_with_iri(entry["airport_iri"].value)
            ratio = fuzz.token_sort_ratio(query, airport_name.lower())
            entry["search_weight_ratio"] = ratio
            print(airport_name, query, ratio)
        sorted_results = sorted(matching_results, key=lambda x:x["search_weight_ratio"], reverse=True)

    else:
        ## Find similar with fuzzy search
        local_data_wrapper.setQuery(f"""                                
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX v:<{base_iri}/data/verb/>

        SELECT ?airport_iri ?airport_name ?region_name ?country_name WHERE {{
            ?airport_iri a [rdfs:label "Airport"];
                rdfs:label ?airport_name;
        }}
        """)

        raw_results = local_data_wrapper.query().bindings
        MINIMUM_RATIO = 70
        MAXIMUM_RESULTS = 3
        legible_results = []
        for entry in raw_results:
            airport_name = entry["airport_name"].value
            ratio = fuzz.partial_ratio(airport_name.lower(), query)

            if ratio >= MINIMUM_RATIO:
                entry["search_weight_ratio"] = ratio
                entry["airport_iri"].value = replace_uri_with_iri(entry["airport_iri"].value)
                print(entry)
                legible_results.append(entry)

        ## Sort top similar results
        if len(legible_results) > 0:
            sorted_similars = sorted(legible_results, key=lambda x:x["search_weight_ratio"], reverse=True)[:MAXIMUM_RESULTS]
    
    context = {
        'page_title': "Search results for \"" + request.GET.get("q") + "\"",
        'search_results': sorted_results,
        'similar_results': sorted_similars,
    }
    response = render(request, 'search_results.html', context)
    return response
    
def airport_detail(request, airport_iri):
    ''' Menampilkan halaman detail bandara '''
    
    local_data_wrapper = SPARQLWrapper2(local_rdf)

    ## Get airport details
    local_data_wrapper.setQuery(get_airport_detail(airport_iri))
    raw_results = local_data_wrapper.query().bindings
    raw_results[0]['countryIRI'].value = replace_uri_with_iri(raw_results[0]['countryIRI'].value)
    raw_results[0]['runways'].value = process_runways(raw_results[0]['runways'].value)
    raw_results[0]['latitudeDeg'].value = float(raw_results[0]['latitudeDeg'].value)
    raw_results[0]['longitudeDeg'].value = float(raw_results[0]['longitudeDeg'].value)

    if raw_results[0]['hasScheduledService'].value == "true":
        raw_results[0]['hasScheduledService'].value = "Yes"
    else:
        raw_results[0]['hasScheduledService'].value = "No"

    local_data_wrapper.setQuery(get_navaids(airport_iri))
    raw_navaids = local_data_wrapper.query().bindings
    navaids_data = process_navaids(raw_navaids[0]['navaids'].value)
    if navaids_data != []:
        navaids_data[0]['countryIRI'] = replace_uri_with_iri(navaids_data[0]['countryIRI'])

    ## Attempt to get more relevant information from remote source DBPedia
    dbpedia_data_wrapper = SPARQLWrapper2("http://dbpedia.org/sparql")
    airport_name = raw_results[0]['airportName'].value.replace("-", "–")

    dbpedia_data_wrapper.setQuery(f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbp: <http://dbpedia.org/property/>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT ?resource_page ?abstract ?thumbnail ?openedDate
    WHERE {{
        ?resource_page a <http://dbpedia.org/ontology/Airport> ;
                dbo:abstract ?abstract ;
                dbp:name "%s"@en ;
                dbp:opened ?openedDate .
        FILTER (LANG(?abstract) = "en")
        OPTIONAL {{ ?resource_page dbo:thumbnail ?thumbnail. }}
    }} LIMIT 1
    """ % airport_name)

    dbpedia_data = dbpedia_data_wrapper.query().bindings
    if len(dbpedia_data) == 0:
        dbpedia_data = []
    else:
        dbpedia_data = dbpedia_data[0]
    
    context = {
        'page_title': airport_name,
        'airport_detail': raw_results[0],
        'dbpedia_data': dbpedia_data,
        'airport_iri': airport_iri,
        'navaids_data': navaids_data
    }

    response = render(request, 'airport_detail.html', context)
    return response

def process_runways(runways_data):
    runways = runways_data.split(";")
    processed_runways = []

    if runways_data == "- - - - - -":
        return []
    
    for runway in runways:
        # Split each runway data by space
        runway_params = runway.split(" ")

        # Create a dictionary for each runway
        runway_dict = {
            "length": runway_params[0] if len(runway_params) > 0 else "-",
            "width": runway_params[1] if len(runway_params) > 1 else "-",
            "surfaceType": runway_params[2] if len(runway_params) > 2 else "-",
            "isLighted": runway_params[3] if len(runway_params) > 3 else "-",
            "isClosed": runway_params[4] if len(runway_params) > 4 else "-",
            "lowerIdent": runway_params[5] if len(runway_params) > 5 else "-",
        }

        # Add the dictionary to the list of processed runways
        processed_runways.append(runway_dict)

    return processed_runways

def country_detail(request, country_iri):
    climate_type_mapping = {
        "1": "Dry tropical or tundra and ice, classification B and E",
        "2": "Wet tropical, classification A",
        "3": "Temperate humid subtropical and temperate continental, classification Cfa, Cwa, and D",
        "4": "Dry hot summers and wet winters"
    }

    ''' Menampilkan halaman detail negara '''
    
    # Initialize SPARQLWrapper for the first query
    country_iri_param = country_iri
    local_data_wrapper = SPARQLWrapper2(local_rdf)
    country_iri = country_iri.replace('_', ' ').title().replace(' ', '_')
    country_iri = "<http://world-airports-kg.up.railway.app/data/"+country_iri+">"

    local_data_wrapper.setQuery(f"""                                 
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>
    
    SELECT DISTINCT ?countryName 
        ?populationCount 
        ?locatedIn 
        ?areaSize 
        ?populationDensity 
        ?coastlineRatio 
        ?netMigration 
        ?infantMortalityRate 
        ?gdpInUSD 
        ?literacyPercentage 
        ?phonesPerThousand 
        ?arableLandPercentage 
        ?cropsLandPercentage 
        ?otherLandPercentage 
        ?birthrate 
        ?deathrate 
        ?agricultureGDP 
        ?industryGDP 
        ?serviceGDP 
        ?climateType
    WHERE {{
        {country_iri} 
            rdfs:label ?countryName ;
            v:populationCount ?populationCount ;
            v:locatedIn ?locatedIn ;
            v:areaSize ?areaSize ;
            v:populationDensity ?populationDensity ;
            v:coastlineRatio ?coastlineRatio ;
        
        OPTIONAL {{ {country_iri} rdfs:label ?countryName . }}          
        OPTIONAL {{ {country_iri} v:netMigration ?netMigration . }}
        OPTIONAL {{ {country_iri} v:infantMortalityRate ?infantMortalityRate . }}
        OPTIONAL {{ {country_iri} v:gdpInUSD ?gdpInUSD . }}
        OPTIONAL {{ {country_iri} v:literacyPercentage ?literacyPercentage . }}
        OPTIONAL {{ {country_iri} v:phonesPerThousand ?phonesPerThousand . }}
        OPTIONAL {{ {country_iri} v:arableLandPercentage ?arableLandPercentage . }}
        OPTIONAL {{ {country_iri} v:cropsLandPercentage ?cropsLandPercentage . }}
        OPTIONAL {{ {country_iri} v:otherLandPercentage ?otherLandPercentage . }}
        OPTIONAL {{ {country_iri} v:birthrate ?birthrate . }}
        OPTIONAL {{ {country_iri} v:deathrate ?deathrate . }}
        OPTIONAL {{ {country_iri} v:agricultureGDP ?agricultureGDP . }}
        OPTIONAL {{ {country_iri} v:industryGDP ?industryGDP . }}
        OPTIONAL {{ {country_iri} v:serviceGDP ?serviceGDP . }}
        OPTIONAL {{ {country_iri} v:climateType ?climateType . }}
    }}""")

    country_details = local_data_wrapper.query().bindings
    for item in country_details:
        climate_value = item.get("climateType").value if item.get("climateType") else ""
        item["climateType_description"] = climate_type_mapping.get(climate_value, "Other Climate Classification")

        # List of numeric fields to format
        numeric_fields = [
            "populationCount", "netMigration", "infantMortalityRate", "gdpInUSD", "literacyPercentage", 
            "phonesPerThousand", "arableLandPercentage", "cropsLandPercentage", "otherLandPercentage", 
            "birthrate", "deathrate", "agricultureGDP", "industryGDP", "serviceGDP", "areaSize", "coastlineRatio", "populationDensity"
        ]

        for field in numeric_fields:
            if field in item:
                try:
                    value = float(item[field].value)
                    if value.is_integer():
                        formatted_value = "{:,.0f}".format(value)
                    else:  
                        formatted_value = "{:,.3f}".format(value) 
                    item[field].value = formatted_value
                except ValueError:
                    pass


    local_data_wrapper = SPARQLWrapper2(local_rdf)
    
    local_data_wrapper.setQuery(f"""                                 
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>
    
    SELECT DISTINCT ?airport_name ?region ?country_iri ?airport_iri WHERE {{
        ?airport_iri a [rdfs:label "Airport"];
                    rdfs:label ?airport_name ;
                    v:airportType ?airport_type;
                    v:region ?region .
        ?region v:countryCode [v:country {country_iri}]
    }} LIMIT 100 """)

    airports = local_data_wrapper.query().bindings

    for airport in airports:
        airport["airport_iri"].value = replace_uri_with_iri(airport["airport_iri"].value)

    dbpedia_country_name = country_iri_param.replace('_', ' ').title()
    dbpedia_data_wrapper = SPARQLWrapper2("http://dbpedia.org/sparql")
    dbpedia_data_wrapper.setQuery("""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbp: <http://dbpedia.org/property/>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT ?resource_page ?thumbnail ?conventionalLongName
    WHERE {
        ?resource_page a <http://dbpedia.org/ontology/Country> ;
                dbo:thumbnail ?thumbnail ;
                dbp:conventionalLongName ?conventionalLongName ;
                rdfs:label "%s" @en .
    } LIMIT 1
    """ % dbpedia_country_name)

    dbpedia_data = dbpedia_data_wrapper.query().bindings
     
    context = {
        'page_title': country_details[0]["countryName"].value,
        'country_details': country_details[0],
        'airports': airports,
        'dbpedia_data': dbpedia_data
    }
    return render(request, 'country_detail.html', context)

def process_navaids(navaids_data):
    navaids = navaids_data.split(";")
    processed_navaids = []

    if navaids_data == "-%-%-%-%-%-%-%-%-%-%-%-":
        return []
    
    for navaid in navaids:
        # Split each runway data by space
        navaid_params = navaid.split("%")
        print(navaid_params)
        print(len(navaid_params))

        # Create a dictionary for each runway
        navaid_dict = {
            "name": navaid_params[0] if len(navaid_params) > 0 else "-",
            "navType": navaid_params[1] if len(navaid_params) > 1 else "-",
            "freq": navaid_params[2] if len(navaid_params) > 2 else "-",
            "coordinates": f"{float(navaid_params[3])}, {float(navaid_params[4])}" if len(navaid_params) > 4 else "-",
            "elevationFt": navaid_params[5] if len(navaid_params) > 5 else "-",
            "countryIRI": navaid_params[6] if len(navaid_params) > 6 else "-",
            "countryName": navaid_params[7] if len(navaid_params) > 7 else "-",
            "magneticVarDeg": float(navaid_params[8]) if len(navaid_params) > 8 else "-",
            "usageType": navaid_params[9] if len(navaid_params) > 9 else "-",
            "powerUsage": navaid_params[10] if len(navaid_params) > 10 else "-",
            "navId": navaid_params[11] if len(navaid_params) > 11 else "-"
        }

        ## Convert to legible name
        navType = navaid_dict["navType"]
        if navType == "VOR":
            navaid_dict["navTypeInfo"] = "Civilian VOR without a colocated DME."
        elif navType == "VOR-DME":
            navaid_dict["navTypeInfo"] = "Civilian VOR with a colocated DME."
        elif navType == "VORTAC":
            navaid_dict["navTypeInfo"] = "Civilian VOR colocated with a military TACAN (also usable as a DME)."
        elif navType == "TACAN":
            navaid_dict["navTypeInfo"] = "Military TACAN without a colocated civilian VOR, usable by civilians as a DME."
        elif navType == "NDB":
            navaid_dict["navTypeInfo"] = "Non-directional beacon without a colocated DME."
        elif navType == "NDB-DME":
            navaid_dict["navTypeInfo"] = "Non-direction beacon with a colocated DME."
        elif navType == "DME":
            navaid_dict["navTypeInfo"] = "Standalone distance-measuring equipment."
        
        usageType = navaid_dict["usageType"]
        if usageType == "HI":
            navaid_dict["usageTypeInfo"] = "High-altitude airways"
        elif usageType == "LO":
            navaid_dict["usageTypeInfo"] = "Low-altitude airways"
        elif usageType == "BOTH":
            navaid_dict["usageTypeInfo"] = "High- and low-altitude airways"
        elif usageType == "TERM":
            navaid_dict["usageTypeInfo"] = "Terminal-area navigation only"
        elif usageType == "RNAV":
            navaid_dict["usageTypeInfo"] = "Non-GPS area navigation"

        # Add the dictionary to the list of processed runways
        processed_navaids.append(navaid_dict)

    return processed_navaids

