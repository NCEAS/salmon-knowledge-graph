
import re
import argparse
import os
import numpy

import pandas as pd 
from pandas import read_html, Series, DataFrame, json_normalize 
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, TIME, XSD, SOSA, ORG
from rdflib.namespace import DefinedNamespace
from rdflib.namespace._GEO import GEO
from shapely.geometry import Point
from shapely import box, geometry
from bs4 import BeautifulSoup
import urllib.request
import ssl
from datetime import datetime



SASAP_ENDPOINT = "https://knb.ecoinformatics.org/knb/"

SASAPR = Namespace(f"{SASAP_ENDPOINT}lod/resource/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("https://qudt.org/vocab/unit/")
ODO = Namespace("http://purl.dataone.org/odo/")
OBOE = Namespace("http://ecoinformatics.org/oboe/oboe.1.2/oboe-core.owl#")

class SASAP_ONT(DefinedNamespace):
    """a shortcut namespace with some enumerated classes/predicates used
    in this script
    """
    # Classes
    DailyEscapementCount_ObservationCollection: URIRef
    ObservationCollection: URIRef
    DailyEscapementCount_Observation: URIRef
    Observation: URIRef
    SALMON_00000676: URIRef
    DailyEscapementCount_Measurement: URIRef
    Measurement: URIRef
    GeographicCoverage: URIRef
    Region: URIRef

    # Object properties
    hasTemporalContext: URIRef
    locatedIn: URIRef
    withinGeographicExtent: URIRef

    # Data properties
    hasValue: URIRef

    _NS = Namespace(f"{SASAP_ENDPOINT}lod/ontology/")

_PREFIX = {
    "sasap-r": SASAPR,
    "sasap-ont": SASAP_ONT._NS,
    "geo": Namespace("http://www.opengis.net/ont/geosparql#"),
    "geof": Namespace("http://www.opengis.net/def/function/geosparql/"),
    "sf": Namespace("http://www.opengis.net/ont/sf#"),
    "wd": Namespace("http://www.wikidata.org/entity/"),
    "wdt": Namespace("http://www.wikidata.org/prop/direct/"),
    "rdf": RDF,
    "rdfs": RDFS,
    "xsd": XSD,
    "owl": OWL,
    "time": TIME,
    "dbo": Namespace("http://dbpedia.org/ontology/"),
    "time": Namespace("http://www.w3.org/2006/time#"),
    "ssn": Namespace("http://www.w3.org/ns/ssn/"),
    "sosa": Namespace("http://www.w3.org/ns/sosa/"),
    "oboe-core": OBOE,
    "odo": ODO
}
SALMON_TYPE_NAMED_INDIVIDUALS = {
    "sockeye": ODO["SALMON_00000517"],
    "coho": ODO["SALMON_00000515"],
    "chinook": ODO["SALMON_00000513"]
}
dataset_doi = 'MW2FJ9' 

def graphify_data(df: DataFrame, boundingPolygon, geo_description) -> Graph:
    graph = Graph()
    # Add location geometry to the graph
    geo_description_formatted = re.sub(' ', '', geo_description)
    geo_coverage_uri = SASAPR[f"geo_coverage.{dataset_doi}"]
    p = RDF.type
    o = GEO.Feature
    graph.add((geo_coverage_uri, p, o))
    o = SASAP_ONT.GeographicCoverage
    graph.add((geo_coverage_uri, p, o))

    p = RDFS.label
    o = Literal(geo_description, datatype=XSD.string)
    graph.add((geo_coverage_uri, p, o))

    wkt = boundingPolygon.wkt
    geometry_uri = SASAPR[f"geometry.boundingPolygon.{dataset_doi}"]
    p = GEO.hasGeometry
    graph.add((geo_coverage_uri, p, geometry_uri))

    p = _PREFIX["geo"]["hasDefaultGeometry"]
    graph.add((geo_coverage_uri, p, geometry_uri))

    p = RDF.type
    o = GEO.Geometry
    graph.add((geometry_uri, p, o))

    o = _PREFIX["sf"]["Polygon"]
    graph.add((geometry_uri, p, o))

    p = GEO.asWKT
    o = Literal(wkt, datatype=GEO.wktLiteral)
    graph.add((geometry_uri, p, o))


    for _, row in df.iterrows():
        date = row["sampleDate"]
        species = row["Species"]
        dailyCount = row["DailyCount"]
        location = row["Location"]
        sasapRegion = row["SASAP.Region"]

        location_formatted = re.sub(' ', '', location)
        sasapRegion_formatted = re.sub(' ', '', sasapRegion)
        sampled_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').date()

        location_uri = SASAPR[f"location.{location_formatted}"]
        p = RDF.type
        o = GEO.Feature
        graph.add((location_uri, p, o))
        o = SOSA.FeatureOfInterest
        graph.add((location_uri, p, o))
        o = ODO.SALMON_00000676
        graph.add((location_uri, p, o))

        p = RDFS.label
        o = Literal(location, datatype=XSD.string)
        graph.add((location_uri, p, o))

        region_uri = SASAPR[f"sasapRegion.{sasapRegion_formatted}"]
        p = RDF.type
        o = SASAP_ONT.Region
        graph.add((region_uri, p, o))

        p = SASAP_ONT.locatedIn
        graph.add((location_uri, p, region_uri))

        p = RDFS.label
        o = Literal(sasapRegion, datatype=XSD.string)
        graph.add((region_uri, p, o))

        if (numpy.isnan(dailyCount)):
            print("No count information available")
        else:
            obc_uri = SASAPR[f"observationCollection.{location_formatted}.{sampled_date}"]
            p = RDF.type
            o = SASAP_ONT.DailyEscapementCount_ObservationCollection
            graph.add((obc_uri, p, o))
            o = SASAP_ONT.ObservationCollection
            graph.add((obc_uri, p, o))

            p = RDFS.label
            o = Literal('Salmon escapement counts observation collecion at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((obc_uri, p, o))

            time_iri = SASAPR[f"date.{sampled_date}"]
            p = SASAP_ONT.hasTemporalContext
            graph.add((obc_uri, p, time_iri))

            s = time_iri
            p = TIME.inXSDDate
            o = Literal(sampled_date, datatype=XSD.date)
            graph.add((s, p, o))

            p = SOSA.hasFeatureOfInterest
            graph.add((obc_uri, p, location_uri))

            ob_uri = SASAPR[f"observation.{location_formatted}.{sampled_date}.{species}"]
            p = RDF.type
            o = SASAP_ONT.DailyEscapementCount_Observation
            graph.add((ob_uri, p, o))
            o = SASAP_ONT.Observation
            graph.add((ob_uri, p, o))

            p = RDFS.label
            o = Literal('Salmon escapement counts observation for '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ob_uri, p, o))

            p = OBOE.hasMember
            graph.add((obc_uri, p, ob_uri))

            # o get named individual of salmon from Salmon Ontology
            if(species in SALMON_TYPE_NAMED_INDIVIDUALS):
                p = OBOE.ofEntity
                o = SALMON_TYPE_NAMED_INDIVIDUALS[species]
                graph.add((ob_uri, p, o))

            ms_uri = SASAPR[f"measurement.{location_formatted}.{sampled_date}.{species}"]
            p = RDF.type
            o = SASAP_ONT.DailyEscapementCount_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Daily Count for '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(dailyCount, datatype=XSD.integer)
            graph.add((ms_uri, p, o))

    return graph

if __name__ == "__main__":

    # Reading the data inside the xml file to a variable under the name data
    context = ssl._create_unverified_context()
    file = urllib.request.urlopen('https://knb.ecoinformatics.org/knb/d1/mn/v2/object/doi%3A10.5063%2FMW2FJ9', context=context)
    metadata = file.read()
    file.close()

    # Passing the stored data inside the beautifulsoup parser, storing the returned object 
    Bs_metadata = BeautifulSoup(metadata, "xml")

    # Finding all instances of tag `unique`
    #b_unique = Bs_metadata.find_all('geographicCoverage')
    b_unique = Bs_metadata.find('geographicCoverage')

    print(b_unique)
    geo_description = b_unique.find('geographicDescription').text
    minx = b_unique.find('westBoundingCoordinate').text
    maxx = b_unique.find('eastBoundingCoordinate').text
    miny = b_unique.find('southBoundingCoordinate').text
    maxy = b_unique.find('northBoundingCoordinate').text

    poly = geometry.Polygon(((minx,miny), (minx,maxy), (maxx,maxy), (maxx,miny)))

    # Read the data file 
    data_file = urllib.request.urlopen('https://knb.ecoinformatics.org/knb/d1/mn/v2/object/knb.92053.1', context=context)
    df = pd.read_csv(data_file, encoding="ISO-8859-1", engine='python')
    data_file.close()

    output_folder = "output"

    os.makedirs(output_folder, exist_ok=True)

    graph = graphify_data(df, poly, geo_description)
    destination = os.path.join(output_folder, f"doi_{dataset_doi}.ttl")
    for prefix in _PREFIX:
        graph.bind(prefix, _PREFIX[prefix])
    
    
    graph.serialize(destination, format="ttl")

    print(f"Writing RDF information to {output_folder}...")






