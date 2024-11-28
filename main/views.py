from django.shortcuts import render
from SPARQLWrapper import SPARQLWrapper, JSON
from fuzzywuzzy import fuzz, process
import environ

# Setup SPARQL
env = environ.Env()
environ.Env.read_env()
sparql = SPARQLWrapper(env("DEPLOYED_GRAPHDB_URL") or "http://localhost:7200/repositories/tk2-airports")
sparql.setReturnFormat(JSON)

# Create your views here.
def index(request):
    ''' Menampilkan halaman utama '''
    return render(request, "index.html")

def search(request):
    ''' Menampilkan hasil pencarian '''

    query = request.GET.get("q").lower()
    sparql.setQuery("""
    PREFIX v: <http://world-airports-kg.up.railway.app/data/verb/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    select ?airport_name where {
        ?s a [rdfs:label "Airport"]; rdfs:label ?airport_name .
        FILTER contains(LCASE(?airport_name),"%s") .
    } limit 100
    """ % query)
    
    results = sparql.queryAndConvert()
    context = {
        'search_results': results["results"]["bindings"],
    }
    response = render(request, 'search_results.html', context)
    return response
    