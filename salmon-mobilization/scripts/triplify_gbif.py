
import re
import argparse
import os


import pandas as pd 
from pandas import read_html, Series, DataFrame, json_normalize 
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, TIME, XSD, SOSA, ORG
from rdflib.namespace import DefinedNamespace
from rdflib.namespace._GEO import GEO
from shapely.geometry import Point
from shapely import box, geometry
from shapely.wkt import loads
from shapely.errors import WKTReadingError
from bs4 import BeautifulSoup
import urllib.request
import ssl
from datetime import datetime
import math



GBIF_ENDPOINT = "https://knb.ecoinformatics.org/knb/gbif/"

GBIF_RESOURCE = Namespace(f"{GBIF_ENDPOINT}lod/resource/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("https://qudt.org/vocab/unit/")
ODO = Namespace("http://purl.dataone.org/odo/")
OBOE = Namespace("http://ecoinformatics.org/oboe/oboe.1.2/oboe-core.owl#")
FO = Namespace("http://purl.dataone.org/fish-ont/")
SO = Namespace("http://purl.dataone.org/salmon-ont/")
KWGR = Namespace("http://stko-kwg.geog.ucsb.edu/lod/resource/")
PROV = Namespace("https://www.w3.org/TR/prov-o/")

class GBIF_ONT(DefinedNamespace):
    """a shortcut namespace with some enumerated classes/predicates used
    in this script
    """
    # Classes
    ObservationPoint: URIRef
    River: URIRef
    ObservationCollection: URIRef
    Observation: URIRef
    Measurement: URIRef

    # Data properties
    gbif_ID: URIRef
    occurenceID: URIRef

    _NS = Namespace(f"{GBIF_ENDPOINT}lod/ontology/")

_PREFIX = {
    "gbifr": GBIF_RESOURCE,
    "gbif-ont": GBIF_ONT._NS,
    "fish-ont": FO,
    "salmon-ont": SO,
    "kwgr": KWGR,
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
    "odo": ODO,
    "prov-o": PROV
}
WATERBODY_DETAILS = {
    "scorff-river": "Scorff River",
    "nivelle-river": "Nivelle River",
    "oir-river": "Oir River",
    "bresle-river": "Bresle River"
}

SALMON_OBSERVATION_PROTOCOL = {
("trapping", "Sampling by trapping", "samplingProtocol.Trapping"),
("sai", "Survey of Salmon abundance Indices", "samplingProtocol.SAI")
}

METADATA_DETAILS = {
    "trapping_scorff-river": ["https://doi.org/10.15468/yvcw8n","2024-03-12", "Since 1995, monitoring has been carried out to observe migration phenology and quantify the abundance of migratory salmon in the Scorff basin. In the downstream part of the Scorff River, a trapping system controls salmon migration by means of 2 traps, one for the descending fish and the other for the ascending fish. On this occasion, biometric characteristics are developed to characterize the population in order to feed this data set.", "Phenology and biological traits of migrating salmon (Salmo salar) sampled by trapping in the Scorff river (France)."],
    "trapping_nivelle-river": ["https://doi.org/10.15468/wf2bg6", "2024-03-13", "Since 1984, monitoring has been carried out to observe migration phenology and quantify the abundance of migratory adults atlantic salmon in Nivelle basin. A trapping system controls adults salmon migration by means of 2 traps, one in the downstream part and an other upstream to estimate the effectiveness. On this occasion, biometric characteristics are developed to characterize the population in order to feed this data set.", "Phenology and biological traits of adult migrating atlantic salmon (Salmo salar) sampled by trapping in the survey in the Nivelle river (France)."],
    "trapping_oir-river": ["https://doi.org/10.15468/k6euut", "2024-03-12", "Since 1984, monitoring has been carried out to observe migration phenology and quantify the abundance of migratory salmon in the Oir basin. In the downstream part of the Oir River, a trapping system controls salmon migration by means of 2 traps, one for the descending fish and the other for the ascending fish. On this occasion, biometric characteristics are developed to characterize the population in order to feed this data set.", "Phenology and biological traits of migrating salmon (Salmo salar) sampled by trapping in the survey in the Oir river (France)."],
    "trapping_bresle-river": ["https://doi.org/10.15468/rrh3nq", "2024-03-12", "Since 1982, migratory salmon have been captured on the Bresle basin to observe migration phenology and quantify their abundance. 15 km from the river estuary a trapping system controls salmon migration and since 1994 an upstream trap captures salmon in their upstream migration 3 km from the estuary. On the occasion of the capture, biometric characteristics are taken to characterize the population in order to feed this data set.", "Phenology and biological traits of migrating salmon (Salmo salar) sampled by trapping in the survey in the Bresle river (France)."],
    "sai_oir-river": ["https://doi.org/10.15468/cjsjrj", "2024-03-12", "Since 1993, an annual campaign is conducted to quantify the abundance of juvenile Atlantic salmon in the Oir basin. It is usually done in September and according to the protocol of Prévost and Baglinière (1995). The electric fishing protocol of Prévost and Baglinière (1995) is used, which is specific to Atlantic salmon young of the year (0+ parr) . Sampling is restrited to areas with shallow running water flowing on coarse bottom substrate i.e. the preferred habitat of young of the year salmon.This data set consists of the abundance and biological traits measured on the fish sampled on this occasion. Observations made on this occasion are descriptive data (species, sex, maturation and biometric (length, weight). In addition, scales samples are taken to determine the age of the fish.", "Abundances and biological traits of the juveniles salmon sampled in the survey of Salmon abundance Indices in the Oir river (France)."],
    "sai_bresle-river": ["https://doi.org/10.15468/chqxig", "2024-03-12", "A survey started in 2016 is conducted every year in early autumn (September to early october) to quantify the abundance of juvenile Atlantic salmon in the Bresle In Normandy. The electrofishing protocol of Prévost and Baglinière (1995) is used. It targets Atlantic salmon young of the year (0+ parr), but older fish (juvenile salmon ≥1+) are also caught and included in this dataset. Sampling is restricted to areas with shallow running water flowing on coarse bottom substrate, i.e. the preferred habitat of young of the year salmon. The data consist of abundance indices and biological traits measured on the fish sampled: length, weight and age. The latter is ascertained from scale samples taken from the fish which size does not allow to determine their age unambiguously. The survey is carried out under the Research Observatory on Diadromes Fishes in Coastal Streamss (ERO DiaPFC) program. The data are stored in the database of the ERO. They are used to develop predictive models and tools for providing scientific advice to improve the management of this heritage species.","Abundances and biological traits of the juveniles salmon sampled in the survey of Salmon abundance Indices in the Bresle river (France)."],
    "sai_nivelle-river": ["https://doi.org/10.15468/alsjvy", "2024-03-12", "A survey started in 2003 is conducted every year in early autumn (late September to early October) to quantify the abundance of juvenile Atlantic salmon in the Nivelle in Pays Basque. The electric fishing protocol of Prévost and Baglinière (1995) is used. It targets Atlantic salmon young of the year (0+ parr), but older fish (juvenile salmon ≥1+) are also caught and included in this dataset. Sampling is restricted to areas with shallow running water flowing on coarse bottom substrate, i.e. the preferred habitat of young of the year salmon. The data consist of abundance indices and biological traits measured on the fish sampled: sex, maturity status, length, weight and age. The latter is ascertained from scale samples taken from the fish which size does not allow to determine their age unambiguously. The survey is carried out under the Research Observatory on Diadromes Fishes in Coastal Streamss (ERO DiaPFC) program. The data are stored in the database of the ERO. They are used to develop predictive models and tools for providing scientific advice to improve the management of this heritage species.","Abundances and biological traits of the juveniles salmon sampled in the survey of Salmon abundance Indices in the Nivelle river (France)."],
    "sai_scorff-river": ["https://doi.org/10.15468/mz4lyw", "2024-03-12", "A survey started in 1993 is conducted every year in early autumn (late September to early October) to quantify the abundance of juvenile Atlantic salmon in the Scorff In Brittany. The electric fishing protocol of Prévost and Baglinière (1995) is used. It targets Atlantic salmon young of the year (0+ parr), but older fish (juvenile salmon ≥1+) are also caught and included in this dataset. Sampling is restricted to areas with shallow running water flowing on coarse bottom substrate, i.e. the preferred habitat of young of the year salmon. The data consist of abundance indices and biological traits measured on the fish sampled: sex, maturity status, length, weight and age. The latter is ascertained from scale samples taken from the fish which size does not allow to determine their age unambiguously. The survey is carried out under the Research Observatory on Diadromes Fishes in Coastal Streamss (ERO DiaPFC) program. The data are stored in the database of the ERO. They are used to develop predictive models and tools for providing scientific advice to improve the management of this heritage species.", "Abundances and biological traits of the juveniles salmon sampled in the survey of Salmon abundance Indices in the Scorff river (France)."]
}
       
dataset_doi = '251GKK' 

def graphify(df: DataFrame, file) -> Graph:
    graph = Graph()
    for _, row in df.iterrows():
        gbif_ID = row["gbifID"]
        occurence_ID = row["occurrenceID"]
        occurence_status = row["occurrenceStatus"]
        country_code = row["countryCode"]
        decimal_latitude = row["decimalLatitude"]
        decimal_longitude = row["decimalLongitude"]
        event_date = row["eventDate"]
        species_code = str(row["speciesKey"])

        waterbodyName = file.split("_")[2]
        protocol = file.split("_")[1]
        waterbody_uri = GBIF_RESOURCE[f"river.{waterbodyName}"]
        p = RDF.type
        o = GEO.Feature
        graph.add((waterbody_uri, p, o))
        o = GBIF_ONT.River
        graph.add((waterbody_uri, p, o))

        waterbody_label = WATERBODY_DETAILS[waterbodyName]
        p = RDFS.label
        o = Literal(waterbody_label, datatype=XSD.string)
        graph.add((waterbody_uri, p, o))

        observationPoint_uri = GBIF_RESOURCE[f"observationPoint.{gbif_ID}"]
        p = RDF.type
        o = GBIF_ONT.ObservationPoint
        graph.add((observationPoint_uri, p, o))

        p = FO.locatedIn
        graph.add((observationPoint_uri, p, waterbody_uri))

        if (country_code == "FR"):
            p = FO.associatedRegion
            o = KWGR[f'administrativeRegion.FRA']
            graph.add((waterbody_uri, p, o))
            graph.add((observationPoint_uri, p, o))


        observationCollection_uri = GBIF_RESOURCE[f"observationCollection.{event_date}"]
        p = RDF.type
        o = GBIF_ONT.ObservationCollection
        graph.add((observationCollection_uri, p, o))

        eventDate_uri = GBIF_RESOURCE[f"timeInstant.{event_date}"]
        p = RDF.type
        o = TIME.Instant
        graph.add((eventDate_uri, p, o))

        p = FO.hasTemporalContext
        graph.add((observationCollection_uri, p, eventDate_uri))

        p = XSD.inXSDDate
        o = Literal(event_date, datatype=XSD.date)
        graph.add((eventDate_uri, p, o))

        if (pd.isna(row["year"])):
            print("No year")
        else:
            p = XSD.inXSDgYear
            o = Literal(int(row["year"]), datatype=XSD.gYear)
            graph.add((eventDate_uri, p, o))

        if (pd.isna(row["month"])):
            print("No month")
        else:
            p = XSD.inXSDgMonth
            o = Literal(int(row["month"]), datatype=XSD.gMonth)
            graph.add((eventDate_uri, p, o))

        if (species_code == "7595433"):
            p = FO.ofSpeciesType
            o = ODO[f'SALMON_00000590']
            graph.add((observationCollection_uri, p, o))
        else:
            print("No species information available")

        p_stage = FO.ofLifeStage
        p_protocol = FO.usesSamplingProtocol
        if (protocol == "trapping"):
            o_stage = SO[f'lifeStage.Migrating']
            o_protocol = SO[f'samplingProtocol.Trapping']
        elif (protocol == "sai"):
            o_stage = SO[f'lifeStage.Juvenile']
            o_protocol = SO[f'samplingProtocol.SAI']
        graph.add((observationCollection_uri, p_stage, o_stage))

        #add metadata
        dataset_name = protocol+ "_"+waterbodyName
        doi = METADATA_DETAILS[dataset_name][0] 
        publication_date = METADATA_DETAILS[dataset_name][1] 
        description = METADATA_DETAILS[dataset_name][2] 
        title = METADATA_DETAILS[dataset_name][3] 

        dataset_uri = OBOE[f"dataset.{dataset_name}"]
        p = RDF.type
        o = OBOE.Dataset
        graph.add((dataset_uri, p, o))
        p = PROV.wasDerivedFrom
        graph.add((observationCollection_uri, p, dataset_uri))

        p = OBOE.doi
        o = Literal(doi, datatype=XSD.anyURI)
        graph.add((dataset_uri, p, o))
        
        p = OBOE.publicationDate
        o = Literal(publication_date, datatype=XSD.date)
        graph.add((dataset_uri, p, o))

        p = OBOE.description
        o = Literal(description, datatype=XSD.string)
        graph.add((dataset_uri, p, o))

        p = OBOE.title
        o = Literal(title, datatype=XSD.string)
        graph.add((dataset_uri, p, o))
        
        if (pd.isna(occurence_status)):
            print("No measurement value")
        else:

            observation_uri = GBIF_RESOURCE[f"observation.{gbif_ID}"]
            p = RDF.type
            o = GBIF_ONT.Observation
            graph.add((observation_uri, p, o))

            p = SOSA.hasMember
            graph.add((observationCollection_uri, p, observation_uri))

            p = GBIF_ONT.gbif_ID
            o = Literal(gbif_ID, datatype=XSD.string)
            graph.add((observation_uri, p, o))

            p = GBIF_ONT.occurenceID
            o = Literal(occurence_ID, datatype=XSD.string)
            graph.add((observation_uri, p, o))

            
            graph.add((observation_uri, p_protocol, o_protocol))
            p = SOSA.hasFeatureOfInterest
            graph.add((observation_uri, p, observationPoint_uri))

            measurement_uri = GBIF_RESOURCE[f"measurement.{gbif_ID}"]
            p = RDF.type
            o = GBIF_ONT.Measurement
            graph.add((measurement_uri, p, o))
            p = OBOE.hasMeasurement
            graph.add((observation_uri, p, measurement_uri))

            p = OBOE.measuresCharacteristic
            o = GBIF_ONT[f'salmonAbundance.OCCURRENCE']
            graph.add((measurement_uri, p, o))
            p = SOSA.observedProperty
            graph.add((observation_uri, p, o))
            if (pd.isnull(occurence_status) or occurence_status == 'N/A'):
                pass
            else:
                o = Literal(occurence_status, datatype=XSD.string)
                p = FO.hasValue
                graph.add((measurement_uri, p, o))
                p = SOSA.hasSimpleResult
                graph.add((observation_uri, p, o))


            observation_value_uri = GBIF_RESOURCE[f"observationValue.{gbif_ID}"]
            p = RDF.type
            o = GBIF_ONT.Observation
            graph.add((observation_uri, p, o))

            p = SOSA.hasMember
            graph.add((observationCollection_uri, p, observation_value_uri))

            p = GBIF_ONT.gbif_ID
            o = Literal(gbif_ID, datatype=XSD.string)
            graph.add((observation_value_uri, p, o))

            p = GBIF_ONT.occurenceID
            o = Literal(occurence_ID, datatype=XSD.string)
            graph.add((observation_value_uri, p, o))

            
            graph.add((observation_value_uri, p_protocol, o_protocol))
            p = SOSA.hasFeatureOfInterest
            graph.add((observation_value_uri, p, observationPoint_uri))

            measurement_value_uri = GBIF_RESOURCE[f"measurementValue.{gbif_ID}"]
            p = RDF.type
            o = GBIF_ONT.Measurement
            graph.add((measurement_value_uri, p, o))
            p = OBOE.hasMeasurement
            graph.add((observation_value_uri, p, measurement_value_uri))

            
            p = OBOE.measuresCharacteristic
            o = GBIF_ONT[f'salmonAbundance.OCCURRENCE_VALUE']
            graph.add((measurement_value_uri, p, o))
            p = SOSA.observedProperty
            graph.add((observation_value_uri, p, o))
            if (pd.isnull(occurence_status) or occurence_status == 'N/A'):
                pass
            else:
                if(occurence_status == "ABSENT"):
                    occurence_status_value = 0
                elif(occurence_status == "PRESENT"):
                     occurence_status_value = 1
                o = Literal(occurence_status_value, datatype=XSD.int)
                p = FO.hasValue
                graph.add((measurement_value_uri, p, o))
                p = SOSA.hasSimpleResult
                graph.add((observation_value_uri, p, o))

        if (decimal_latitude is None):
            print("No geometry exists for observation point")
        else:
            try:
                # print(decimal_latitude)

                geometry = Point([decimal_longitude, decimal_latitude]) 
                if (is_valid_wkt(geometry) == True):
                    geometry_iri = GBIF_RESOURCE[f"geometry.observationPoint.{gbif_ID}"]
                    
                    p = GEO.hasGeometry
                    graph.add((observationPoint_uri, p, geometry_iri))

                    p = _PREFIX["geo"]["hasDefaultGeometry"]
                    graph.add((observationPoint_uri, p, geometry_iri))

                    p = RDF.type
                    o = GEO.Geometry
                    graph.add((geometry_iri, p, o))

                    o = _PREFIX["sf"]["Point"]
                    graph.add((geometry_iri, p, o))

                    label = f"Geometry of the escapement with ID {id}."
                    p = RDFS.label
                    o = Literal(label, datatype=XSD.string)
                    graph.add((geometry_iri, p, o))
                    
                    wkt = geometry.wkt
                    p = GEO.asWKT
                    o = Literal(wkt, datatype=GEO.wktLiteral)
                    graph.add((geometry_iri, p, o))
                else:
                    print("Invalid geometry")
            except Exception:
                print("Geometry error for observation point with ID "+str(gbif_ID))


    return graph
def is_valid_wkt(wkt_literal):
    try:
        # Try to load the WKT literal
        # print(wkt_literal)
        geom = loads(str(wkt_literal))
        return True  # If parsing succeeds, it's valid
    except Exception as error:
        #  print(error)
         return False 
    # except WKTReadingError:
    #     print("Worked")
    #     return False  # If a parsing error occurs, it's invalid
    
if __name__ == "__main__":
    datasets = ["gbif_sai_nivelle-river","gbif_sai_oir-river","gbif_sai_bresle-river","gbif_sai_scorff-river","gbif_trapping_nivelle-river","gbif_trapping_oir-river","gbif_trapping_bresle-river","gbif_trapping_scorff-river"]
    # datasets = ["gbif_sai_bresle-river","gbif_trapping_bresle-river"]

    for file in datasets:
        data_path = "../datasets/gbif/"+file+".csv"
        output_file = file+".ttl"
        df = pd.read_csv(data_path, sep='\t', header=0, encoding='latin-1')
        print(df.keys())
        output_folder = "output"

        os.makedirs(output_folder, exist_ok=True)

        graph = graphify(df, file)
        destination = os.path.join(output_folder, output_file)
        for prefix in _PREFIX:
            graph.bind(prefix, _PREFIX[prefix])
        graph.serialize(destination=destination, format="ttl")
        print(f"Finished writing RDF information to {output_folder}...")





