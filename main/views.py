from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper2
from thefuzz import fuzz, process
import environ

# Setup environment variables
env = environ.Env()
environ.Env.read_env()
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
    # TODO Update with actual query
    local_data_wrapper.setQuery("""
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    select ?airport_name where {
        ?s a [rdfs:label "Airport"]; rdfs:label ?airport_name .
    }
    """)
    raw_results = local_data_wrapper.query().bindings

    ## Filter with fuzzy search
    MINIMUM_RATIO = 70
    print(query)
    legible_results = []
    for entry in raw_results:
        airport_name = entry["airport_name"].value
        ratio = fuzz.token_set_ratio(airport_name.lower(), query)

        if ratio >= MINIMUM_RATIO:
            print(ratio)
            legible_results.append([entry, ratio])

    ## Sort legible results
    sorted_results = sorted(legible_results, key=lambda x:x[1], reverse=True)
    print(sorted_results)
    
    context = {
        'search_results': sorted_results,
    }
    response = render(request, 'search_results.html', context)
    return response
    