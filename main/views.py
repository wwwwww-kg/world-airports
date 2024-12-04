from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

from main.query import get_airport_detail

# Setup environment variables
env = environ.Env()
environ.Env.read_env()
graphdb_host = env("GRAPHDB_HOST")
base_iri = env("BASE_IRI")

# Create your views here.
def index(request):
    ''' Menampilkan halaman utama '''
    return render(request, "index.html")

def search(request):
    ''' Menampilkan hasil pencarian '''

    query = request.GET.get("q").lower()
    local_data_wrapper = SPARQLWrapper2(base_iri)
    ## Get all airports?
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
    }} ORDER BY ?airport_name
    """ % query)

    matching_results = local_data_wrapper.query().bindings
    sorted_results = []
    sorted_similars = []

    if matching_results != []:
        ## Sort results from most relevant
        for entry in matching_results:
            airport_name = entry["airport_name"].value
            ratio = fuzz.partial_token_sort_ratio(query, airport_name.lower())
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

def country_detail(request, IRI):
    ''' Menampilkan halaman detail negara '''
    return

def replace_uri_with_iri(uri):
    iri = uri.replace("http://world-airports-kg.up.railway.app/data/", "")
    return iri

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
