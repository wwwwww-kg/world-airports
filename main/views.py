from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

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
    