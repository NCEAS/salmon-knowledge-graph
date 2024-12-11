
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
    ASL_ObservationCollection: URIRef
    ASL_Observation: URIRef
    SALMON_00000676: URIRef
    ASL_Measurement: URIRef
    Length_Measurement: URIRef
    Sex_Measurement: URIRef
    Age_Measurement: URIRef
    GeographicCoverage: URIRef
    Region: URIRef
    Weight_Measurement: URIRef
    FreshWaterAge_Measurement: URIRef
    SaltWaterAge_Measurement: URIRef
    EuropeanAge_Measurement: URIRef

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
    "chinook": ODO["SALMON_00000513"],
    "chum": ODO["SALMON_00000514"]
}

LENGTH_MEASUREMENT_METHOD_NAMED_INDIVIDUALS = {
    "mid-eye to fork of tail": ODO["SALMON_00000632"],
    "mid-eye to hypural plate": ODO["SALMON_00000633"],
    "post orbit to fork of tail": ODO["SALMON_00000635"],
    "post orbit to hypural plate": ODO["SALMON_00000636"],
    "tip of snout to fork of tail": ODO["SALMON_00000638"],
}
dataset_doi = 'J38QX8' 

def graphify_data(df: DataFrame, geographicCoverages) -> Graph:
    graph = Graph()

    # Get first 10,000 rows from df 
    df_subset = df.iloc[:10000] 
    # Add location geometry to the graph
    coverage_counter = 0
    for coveraage in geographicCoverages:
        coverage_counter = coverage_counter + 1
        geo_description = coveraage.find('geographicDescription').text
        minx = coveraage.find('westBoundingCoordinate').text
        maxx = coveraage.find('eastBoundingCoordinate').text
        miny = coveraage.find('southBoundingCoordinate').text
        maxy = coveraage.find('northBoundingCoordinate').text

        boundingPolygon = geometry.Polygon(((minx,miny), (minx,maxy), (maxx,maxy), (maxx,miny)))

        geo_description_formatted = re.sub(' ', '', geo_description)
        geo_coverage_uri = SASAPR[f"geo_coverage.{dataset_doi}.{coverage_counter}"]
        p = RDF.type
        o = GEO.Feature
        graph.add((geo_coverage_uri, p, o))
        o = SASAP_ONT.GeographicCoverage
        graph.add((geo_coverage_uri, p, o))

        p = RDFS.label
        o = Literal(geo_description, datatype=XSD.string)
        graph.add((geo_coverage_uri, p, o))

        wkt = boundingPolygon.wkt
        geometry_uri = SASAPR[f"geometry.boundingPolygon.{dataset_doi}.{coverage_counter}"]
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


    for _, row in df_subset.iterrows():
        sampleDate = row["sampleDate"]
        projectType = row["ASLProjectType"]
        projectNumber = row["ProjectNumber"]
        location = str(row["Location"])
        sasapRegion = row["SASAP.Region"]
        gear = row["Gear"]
        species = row["Species"]

        length = row["Length"]
        lengthMeasurementType = row["Length.Measurement.Type"]
        
        sex = row["Sex"]
        sexDeterminationMethod = row["Sex.Determination.Method"]
        
        freshWaterAge = row["Fresh.Water.Age"]
        saltWaterAge = row["Salt.Water.Age"]
        europeanAge = row["AgeEuropean"]
        ageError = row["Age.Error"]
        
        weight = row["Weight"]

        location_formatted = re.sub(' ', '', location)
        sex_formatted = re.sub(' ', '', sex)
        sasapRegion_formatted = re.sub(' ', '', sasapRegion)
        sampled_date = datetime.strptime(sampleDate, '%Y-%m-%d').date()

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

        # Observation Collection  Grouping based on location and sampled date
        obc_uri = SASAPR[f"observationCollection.{location_formatted}.{sampled_date}"]
        p = RDF.type
        o = SASAP_ONT.ASL_ObservationCollection
        graph.add((obc_uri, p, o))

        p = RDFS.label
        o = Literal('ASL observation collecion at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
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

        # Observation - Grouping based on species
        ob_uri = SASAPR[f"observation.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
        p = RDF.type
        o = SASAP_ONT.ASL_Observation
        graph.add((ob_uri, p, o))

        p = RDFS.label
        o = Literal('ASL observation for '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
        graph.add((ob_uri, p, o))

        p = OBOE.hasMember
        graph.add((obc_uri, p, ob_uri))

        # To get named individual of salmon from Salmon Ontology
        if(species in SALMON_TYPE_NAMED_INDIVIDUALS):
            p = OBOE.ofEntity
            o = SALMON_TYPE_NAMED_INDIVIDUALS[species]
            graph.add((ob_uri, p, o))
       
        if (numpy.isnan(length)):
            print("No fish length information available")
        else:
            ms_uri = SASAPR[f"lengthMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
            p = RDF.type
            o = SASAP_ONT.Length_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.ASL_Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Fish length measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(length, datatype=XSD.integer)
            graph.add((ms_uri, p, o))

            # To get named individual of measurement type from Salmon Ontology
            if(lengthMeasurementType in SALMON_TYPE_NAMED_INDIVIDUALS):
                p = ODO.measuredUsingMethod
                o = LENGTH_MEASUREMENT_METHOD_NAMED_INDIVIDUALS[lengthMeasurementType]
                graph.add((ms_uri, p, o))
        
        if (numpy.isnan(freshWaterAge)):
            print("No fresh water age information available")
        else:
            ms_uri = SASAPR[f"freshWaterAgeMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
            p = RDF.type
            o = SASAP_ONT.FreshWaterAge_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.ASL_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.Age_Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Fish (fresh water) age measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(freshWaterAge, datatype=XSD.integer)
            graph.add((ms_uri, p, o))

        if (numpy.isnan(saltWaterAge)):
            print("No salt water age information available")
        else:
            ms_uri = SASAPR[f"saltWaterAgeMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
            p = RDF.type
            o = SASAP_ONT.SaltWaterAge_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.ASL_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.Age_Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Fish (salt water) age measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(saltWaterAge, datatype=XSD.integer)
            graph.add((ms_uri, p, o))
        
        if (pd.isnull(europeanAge)):
            print("No european age information available")
        else:
            ms_uri = SASAPR[f"europeanAgeMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
            p = RDF.type
            o = SASAP_ONT.EuropeanAge_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.ASL_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.Age_Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Fish (european) age measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(europeanAge, datatype=XSD.decimal)
            graph.add((ms_uri, p, o))

        if (numpy.isnan(weight)):
            print("No weight information available")
        else:
            ms_uri = SASAPR[f"weightMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
            p = RDF.type
            o = SASAP_ONT.Weight_Measurement
            graph.add((ms_uri, p, o))
            o = SASAP_ONT.ASL_Measurement
            graph.add((ms_uri, p, o))

            p = RDFS.label
            o = Literal('Fish weight measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
            graph.add((ms_uri, p, o))

            p = OBOE.hasMeasurement
            graph.add((ob_uri, p, ms_uri))

            p = SASAP_ONT.hasValue
            o = Literal(weight, datatype=XSD.integer)
            graph.add((ms_uri, p, o))

        ms_uri = SASAPR[f"sexMeasurement.{location_formatted}.{sampled_date}.{species}.{sex_formatted}.{length}.{freshWaterAge}.{saltWaterAge}.{europeanAge}"]
        p = RDF.type
        o = SASAP_ONT.Sex_Measurement
        graph.add((ms_uri, p, o))
        o = SASAP_ONT.ASL_Measurement
        graph.add((ms_uri, p, o))

        p = RDFS.label
        o = Literal('Fish sex measurement corresponding to an observation of '+species+ ' made at '+ location + ' measured on '+ str(sampled_date) + '.', datatype=XSD.string)
        graph.add((ms_uri, p, o))

        p = OBOE.hasMeasurement
        graph.add((ob_uri, p, ms_uri))

        p = SASAP_ONT.hasValu
        o = Literal(sex, datatype=XSD.string)
        graph.add((ms_uri, p, o))

    return graph

if __name__ == "__main__":

    # Reading the data inside the xml file to a variable under the name data
    context = ssl._create_unverified_context()
    file = urllib.request.urlopen('https://knb.ecoinformatics.org/knb/d1/mn/v2/object/doi%3A10.5063%2FJ38QX8', context=context)
    metadata = file.read()
    file.close()

    # Passing the stored data inside the beautifulsoup parser, storing the returned object 
    Bs_metadata = BeautifulSoup(metadata, "xml")

    # Finding all instances of tag `unique`
    #b_unique = Bs_metadata.find_all('geographicCoverage')
    b_unique = Bs_metadata.find_all('geographicCoverage')

    # Read the data file 
    data_file = urllib.request.urlopen('https://knb.ecoinformatics.org/knb/d1/mn/v2/object/urn%3Auuid%3A67908387-a1d2-41d4-a2ef-64be8694495a', context=context)
    df = pd.read_csv(data_file, encoding="ISO-8859-1", engine='python')
    data_file.close()

    output_folder = "output"

    os.makedirs(output_folder, exist_ok=True)

    graph = graphify_data(df, b_unique)
    destination = os.path.join(output_folder, f"doi_{dataset_doi}.ttl")
    for prefix in _PREFIX:
        graph.bind(prefix, _PREFIX[prefix])
    
    
    graph.serialize(destination, format="ttl")

    print(f"Writing RDF information to {output_folder}...")






