from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

# Setup environment variables
env = environ.Env()
environ.Env.read_env()
graphdb_host = env("GRAPHDB_HOST")
base_iri = env("BASE_IRI")

# Helper functions
def replace_uri_with_iri(uri):
    iri = uri.replace(graphdb_host+"/data/", "")
    return iri

def create_uri_from_iri(iri):
    uri = "<" + graphdb_host + "/data/" + iri + ">"
    return uri

# Create your views here.
def index(request):
    ''' Menampilkan halaman utama '''
    return render(request, "index.html")

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

    ## Attempt to get every relevant airport data from local RDF
    local_data_wrapper = SPARQLWrapper2(base_iri)
    airport_uri = create_uri_from_iri(IRI)
    print(airport_uri)

    local_data_wrapper.setQuery("""                                
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>

    SELECT ?airport_name WHERE {
            %s a [rdfs:label "Airport"];
                rdfs:label ?airport_name .
    }
    """ % airport_uri)
    
    airport_data = local_data_wrapper.query().bindings[0]
    print(airport_data)

    ## Attempt to get more relevant information from remote source DBPedia
    dbpedia_data_wrapper = SPARQLWrapper2("http://dbpedia.org/sparql")
    airport_name = airport_data['airport_name'].value
    print(airport_name)

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
    print("DB", dbpedia_data)

    context = {
        'airport_data': airport_data,
        'dpedia_queries': dbpedia_data,
    }
    response = render(request, 'index.html', context)
    return response

def country_detail(request):
    ''' Menampilkan halaman detail negara '''
    return