from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper2, JSON
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
    MINIMUM_RATIO = 50
    print(query)
    weighted_results = process.extract(query, raw_results, scorer=fuzz.token_set_ratio, limit=100)
    legible_results = []
    for (result, ratio) in weighted_results:
        if ratio >= MINIMUM_RATIO:
            legible_results.append(result)
    
    context = {
        'search_results': legible_results,
    }
    response = render(request, 'search_results.html', context)
    return response
    