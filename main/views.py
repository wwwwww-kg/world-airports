from django.shortcuts import render, redirect
from django.urls import reverse
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

from main.query import get_airport_detail

# Setup environment variables
env = environ.Env()
environ.Env.read_env()
graphdb_host = env("GRAPHDB_HOST")
base_iri = env("BASE_IRI")

def replace_uri_with_iri(uri):
    iri = uri.replace(graphdb_host + "/data/", "")
    return iri

def create_uri_from_iri(iri):
    uri = "<" + graphdb_host + "/data/" + iri + ">"
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
    local_data_wrapper = SPARQLWrapper2(base_iri)

    ## Attempt to get basic airport data via SPARQL with FILTER
    local_data_wrapper.setQuery(f"""                                
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>

    SELECT ?airport_iri ?airport_name ?airport_iata ?region_name ?country_name WHERE {{
            ?airport_iri a [rdfs:label "Airport"];
                rdfs:label ?airport_name;
                v:region ?region_node .
            ?region_node rdfs:label ?region_name;
                v:countryCode [v:country [rdfs:label ?country_name]] .
            OPTIONAL {{ ?airport_iri v:iataCode ?airport_iata. }}
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
        PREFIX v:<{graphdb_host}/data/verb/>

        SELECT ?airport_iri ?airport_name ?region_name ?country_name WHERE {{
            ?airport_iri a [rdfs:label "Airport"];
                rdfs:label ?airport_name;
        }}
        """)

        raw_results = local_data_wrapper.query().bindings
        MINIMUM_RATIO = 70
        MAXIMUM_RESULTS = 5
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
        'search_results': sorted_results,
        'similar_results': sorted_similars,
    }
    response = render(request, 'search_results.html', context)
    return response
    
def airport_detail(request, IRI):
    ''' Menampilkan halaman detail bandara '''
    
    local_data_wrapper = SPARQLWrapper2(base_iri)
    ## Get airport details
    local_data_wrapper.setQuery(get_airport_detail(IRI))
    raw_results = local_data_wrapper.query().bindings

    raw_results[0]['countryIRI'].value = replace_uri_with_iri(raw_results[0]['countryIRI'].value)

    raw_results[0]['runways'].value = process_runways(raw_results[0]['runways'].value)

        ## Attempt to get more relevant information from remote source DBPedia
    dbpedia_data_wrapper = SPARQLWrapper2("http://dbpedia.org/sparql")
    airport_name = raw_results[0]['airportName'].value

    dbpedia_data_wrapper.setQuery("""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbp: <http://dbpedia.org/property/>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT ?resource_page ?abstract ?thumbnail
    WHERE {
        ?resource_page a <http://dbpedia.org/ontology/Airport> ;
                dbo:abstract ?abstract ;
                dbp:name "%s"@en .
        FILTER (LANG(?abstract) = "en")
    } LIMIT 1
    """ % airport_name)

    dbpedia_data = dbpedia_data_wrapper.query().bindings

    print(dbpedia_data)

    context = {
        'airport_detail': raw_results[0],
        'dbpedia_data': dbpedia_data[0]
    }

    response = render(request, 'airport_detail.html', context)
    return response

def process_runways(runways_data):
    runways = runways_data.split(";")
    processed_runways = []
    
    for runway in runways:
        # Split each runway data by space
        runway_params = runway.split(" ")

        # Create a dictionary for each runway
        runway_dict = {
            "length": runway_params[0] if len(runway_params) > 0 else "-",
            "width": runway_params[1] if len(runway_params) > 1 else "-",
            "surfaceType": runway_params[2] if len(runway_params) > 2 else "-",
            "isLighted": runway_params[3] if len(runway_params) > 3 else "-",
            "isClosed": runway_params[4] if len(runway_params) > 4 else "-"
        }

        # Add the dictionary to the list of processed runways
        processed_runways.append(runway_dict)

    return processed_runways

def country_detail(request, country_iri_param):
    ''' Menampilkan halaman detail negara '''
    local_data_wrapper = SPARQLWrapper2(base_iri)
    country_iri = country_iri_param.replace('_', ' ').title().replace(' ', '_')
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

    local_data_wrapper = SPARQLWrapper2(base_iri)
    
    local_data_wrapper.setQuery(f"""                                 
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>
    
    SELECT DISTINCT ?airport_name ?region ?country_iri ?airport_iri WHERE {{
        ?airport_iri a [rdfs:label "Airport"];
                    rdfs:label ?airport_name ;
                    v:region ?region .
        ?region v:countryCode [v:country {country_iri}]
    }}""")

    airports = local_data_wrapper.query().bindings

    for airport in airports:
        airport["airport_iri"].value = replace_uri_with_iri(airport["airport_iri"].value)

    dbpedia_country_name = country_iri_param.replace('_', ' ').title()
    dbpedia_data_wrapper = SPARQLWrapper2("http://dbpedia.org/sparql")
    dbpedia_data_wrapper.setQuery("""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbp: <http://dbpedia.org/property/>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT ?resource_page ?abstract ?thumbnail ?conventionalLongName
    WHERE {
        ?resource_page a <http://dbpedia.org/ontology/Country> ;
                dbo:abstract ?abstract ;
                dbo:thumbnail ?thumbnail ;
                dbp:conventionalLongName ?conventionalLongName ;
                rdfs:label "%s" @en .
        FILTER (LANG(?abstract) = "en")
    } LIMIT 1
    """ % dbpedia_country_name)

    dbpedia_data = dbpedia_data_wrapper.query().bindings

    print(len(country_details))
    print(len(airports))
    
    context = {
        'country_details': country_details,
        'airports': airports,
        'dbpedia_data': dbpedia_data
    }
    return render(request, 'country_detail.html', context)
