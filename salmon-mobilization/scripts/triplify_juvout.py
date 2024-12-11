
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
from bs4 import BeautifulSoup
import urllib.request
import ssl
from datetime import datetime
import math



JUVOUT_ENDPOINT = "https://knb.ecoinformatics.org/knb/streamnet/JUVOUT/"
STREAMNETONT = Namespace("https://knb.ecoinformatics.org/knb/streamnet/lod/ontology/")
STREAMNETRES = Namespace("https://knb.ecoinformatics.org/knb/streamnet/lod/resource/")

JUVOUT_RESOURCE = Namespace(f"{JUVOUT_ENDPOINT}lod/resource/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("https://qudt.org/vocab/unit/")
ODO = Namespace("http://purl.dataone.org/odo/")
OBOE = Namespace("http://ecoinformatics.org/oboe/oboe.1.2/oboe-core.owl#")
FO = Namespace("http://purl.dataone.org/fish-ont/")
PROV = Namespace("https://www.w3.org/TR/prov-o/")

class JUVOUT_ONT(DefinedNamespace):
    """a shortcut namespace with some enumerated classes/predicates used
    in this script
    """
    # Classes
    Escapement_Observation: URIRef
    Escapement_Measurement: URIRef
    Observation: URIRef
    SALMON_00000676: URIRef
    CumulativeCount_Measurement: URIRef
    Measurement: URIRef
    GeographicCoverage: URIRef
    Region: URIRef
    Waterbody: URIRef
    Escapement_ObservationCollection: URIRef
    RecoveryDomain: URIRef

    # Object properties
    hasTemporalContext: URIRef
    locatedIn: URIRef
    withinGeographicExtent: URIRef

    # Data properties
    hasValue: URIRef
    populationFitNotes: URIRef
    streamnet_populationID: URIRef
    nmfs_majorPopulationGroup: URIRef
    streamnet_populationName: URIRef
    escapementName: URIRef
    nmfs_populationID: URIRef
    nmfs_populationName: URIRef
    commonPopulationName: URIRef
    esu_dps: URIRef

    _NS = Namespace(f"{JUVOUT_ENDPOINT}lod/ontology/")

_PREFIX = {
    "juvoutr": JUVOUT_RESOURCE,
    "juvout-ont": JUVOUT_ONT._NS,
    "fish-ont": FO,
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
    "streamnet-ont": STREAMNETONT,
    "streamnetr": STREAMNETRES,
    "prov-o": PROV
}
SALMON_TYPE_NAMED_INDIVIDUALS = {
    "sockeye salmon": ODO["SALMON_00000517"],
    "coho salmon": ODO["SALMON_00000515"],
    "chinook salmon": ODO["SALMON_00000513"],
    "chum salmon": ODO["SALMON_00000514"],
    "steelhead": ODO["SALMON_00000570"],
}
SALMON_RUN_TYPE_NAMED_INDIVIDUALS = {
        "Both early & late": STREAMNETONT["runType.Early-Late"],
        "Both summer & winter" : STREAMNETONT["runType.Summer-Winter"],
        "Early" : STREAMNETONT["runType.Early"],
        "Fall" : STREAMNETONT["runType.Fall"],
        "Late" : STREAMNETONT["runType.Late"],
        "Late fall" : STREAMNETONT["runType.LateFall"],
        "Spring" : STREAMNETONT["runType.Spring"],
        "Spring summer" : STREAMNETONT["runType.Spring-Summer"],
        "Summer" : STREAMNETONT["runType.Summer"],
        "Unknown" : STREAMNETONT["runType.Unknown"],
        "Winter" : STREAMNETONT["runType.Winter"]
}
SALMON_MEASUREMENT_CHARACTERISTIC = {      
("TOTALNATURAL", "salmonCharacteristic.TOTALNATURAL"),
("AGE4PLUSPROP", "salmonCharacteristic.;AGE4PLUSPROP"),
("AGE0PROP", "salmonCharacteristic.AGE0PROP"),
("AGE1PROP", "salmonCharacteristic.AGE1PROP"),
("AGE2PROP", "salmonCharacteristic.AGE2PROP"),
("AGE3PROP", "salmonCharacteristic.AGE3PROP")
}
       
dataset_doi = '251GKK' 

def graphify(df: DataFrame) -> Graph:
    graph = Graph()
    # print(df.keys())
    for _, row in df.iterrows():
        common_name = row["ï»¿COMMONNAME"]
        # common_name = row["COMMONNAME"]
        run = row["RUN"].replace("/", " ")
        recovery_domain = row["RECOVERYDOMAIN"]
        esu_dps = row["ESU_DPS"]
        major_population_group = row["MAJORPOPGROUP"]
        population_id = row["POPID"]
        nmfs_pop_id = row["NMFS_POPID"]
        location_name = str(row["LOCATIONNAME"])
        population_name = row["POPULATIONNAME"]
        escap_pop_name = row["ESAPOPNAME"]
        common_pop_name = str(row["COMMONPOPNAME"]).strip()
        pop_fit = row["POPFIT"]
        pop_fit_notes = row["POPFITNOTES"]
        # estimate_type = row["ESTIMATETYPE"]
        # waterbody = row["WATERBODY"]
        out_migration_year = row["OUTMIGRATIONYEAR"]
        contact_agency = row["CONTACTAGENCY"]
        method_number = row["METHODNUMBER"]

        prot_meth_name = row["PROTMETHNAME"] #Name(s) of protocols, data collection, and data analysis methods used to calculate the indicator estimate.
        prot_meth_url = row["PROTMETHURL"] #Links to protocols and methods describing the methodology and documenting the derivation of the indicator.
        method_adjustments = row["METHODADJUSTMENTS"] #Minor adjustments to a method in a given year that are not described in the method citations but are important.
        other_data_sources = row["OTHERDATASOURCES"] #Additional organizations that provided data or expertise to calculate the indicator(s), metric(s), or age distribution.
        comments = row["COMMENTS"] #Comments about this record.
        submit_agency = row["SUBMITAGENCY"] #Indicates who sent each data record to the central database.
        id = row["ID"] #Value used by computer to identify a record.
        update = row["UPDDATE"] #
        update = row["UPDDATE"] #

        # waterbody_formatted = re.sub('[^A-Za-z0-9 ]+', '', waterbody)
        # waterbody_formatted = "".join(waterbody_formatted.split())
        # waterbody_uri = STREAMNETRES[f"waterBody.{waterbody_formatted}"]
        # p = RDF.type
        # o = GEO.Feature
        # graph.add((waterbody_uri, p, o))
        # o = STREAMNETONT.Waterbody
        # graph.add((waterbody_uri, p, o))

        # p = RDFS.label
        # o = Literal(waterbody, datatype=XSD.string)
        # graph.add((waterbody_uri, p, o))

        population_uri = JUVOUT_RESOURCE[f"population.{population_id}"]
        p = RDF.type
        o = JUVOUT_ONT.SalmonPopulation
        graph.add((population_uri, p, o))

        if (~pd.isnull(major_population_group) and major_population_group != 'N/A'):
            p = STREAMNETONT.nmfs_majorPopulationGroup
            o = Literal(major_population_group, datatype=XSD.string)
            graph.add((population_uri, p, o))

        p = STREAMNETONT.streamnet_populationID
        o = Literal(population_id, datatype=XSD.int)
        graph.add((population_uri, p, o))

        p = STREAMNETONT.streamnet_populationName
        o = Literal(population_name, datatype=XSD.string)
        graph.add((population_uri, p, o))

        if (~pd.isnull(escap_pop_name) and escap_pop_name != 'N/A'):
            p = STREAMNETONT.escapementName
            o = Literal(escap_pop_name, datatype=XSD.string)
            graph.add((population_uri, p, o))

        if (~pd.isnull(nmfs_pop_id)):
            p = STREAMNETONT.nmfs_populationID 
            o = Literal(nmfs_pop_id, datatype=XSD.int)
            graph.add((population_uri, p, o))

        if (~pd.isnull(population_name) and ~pd.isna(population_name)):
            p = STREAMNETONT.nmfs_populationName
            o = Literal(population_name, datatype=XSD.string)
            graph.add((population_uri, p, o))

        if common_pop_name == 'nan':
            pass
        else:
            p = STREAMNETONT.commonPopulationName
            o = Literal(common_pop_name, datatype=XSD.string)
            graph.add((population_uri, p, o))

        if (~pd.isnull(esu_dps) and esu_dps != 'N/A'):
            p = STREAMNETONT.esu_dps
            o = Literal(esu_dps, datatype=XSD.string)
            graph.add((population_uri, p, o))

        if pop_fit_notes == 'nan':
            pass
        else:
            p = STREAMNETONT.populationFitNotes
            o = Literal(pop_fit_notes, datatype=XSD.string)
            graph.add((population_uri, p, o))

        recoveryDomain_formatted = recovery_domain.replace(" ", "").replace("/", "")
        recoveryDomain_uri = STREAMNETRES[f"region.{recoveryDomain_formatted}"]
        p = RDF.type
        o = STREAMNETONT.RecoveryDomain
        graph.add((recoveryDomain_uri, p, o))

        o = GEO.Feature
        graph.add((recoveryDomain_uri, p, o))

        p = RDFS.label
        o = Literal(recovery_domain, datatype=XSD.string)
        graph.add((recoveryDomain_uri, p, o))

        p = STREAMNETONT.fallsUnderRegion
        graph.add((population_uri, p, recoveryDomain_uri))

        smoltEqLocation_iri = STREAMNETRES[f"smoltEqLocation.{id}"]
        p = RDF.type
        o = STREAMNETONT.SmoltEQLocation
        graph.add((smoltEqLocation_iri, p, o))
        p = RDF.type
        o = GEO.Feature
        graph.add((smoltEqLocation_iri, p, o))

        if (~pd.isnull(row["SMOLTEQLOCPTCODE"])):
            p = JUVOUT_ONT.smoltEqLocPTCode
            o = Literal(row["SMOLTEQLOCPTCODE"], datatype=XSD.string)
            graph.add((smoltEqLocation_iri, p, o))

        p = FO.associatedRegion
        graph.add((smoltEqLocation_iri, p, recoveryDomain_uri))

        observation_collection_uri = JUVOUT_RESOURCE[f"observationCollection.{id}"]
        p = RDF.type
        o = JUVOUT_ONT.Escapement_ObservationCollection
        graph.add((observation_collection_uri, p, o))
        p = FO.ofSpeciesType
        species_name = common_name.lower()
        o = SALMON_TYPE_NAMED_INDIVIDUALS[species_name]
        graph.add((observation_collection_uri, p, o))

        p = FO.associatedPopulation
        graph.add((observation_collection_uri, p, population_uri))
        
        p = SOSA.hasFeatureOfInterest
        graph.add((observation_collection_uri, p, smoltEqLocation_iri))

        p = FO.hasTemporalContext
        o = Literal(out_migration_year, datatype=XSD.gYear)
        graph.add((observation_collection_uri, p, o))

        p = FO.outMigrationYear
        graph.add((observation_collection_uri, p, o))

        method_uri = STREAMNETRES[f"method.{method_number}"]
        p = RDF.type
        o = STREAMNETONT.EstimationProtocol
        graph.add((method_uri, p, o))

        p = STREAMNETONT.methodName
        o = Literal(prot_meth_name, datatype=XSD.string)
        graph.add((method_uri, p, o))

        p = STREAMNETONT.methodID
        o = Literal(method_number, datatype=XSD.int)
        graph.add((method_uri, p, o))

        p = STREAMNETONT.methodSource_URL
        o = Literal(prot_meth_url, datatype=XSD.IRI)
        graph.add((method_uri, p, o))
            
        for characteristic in SALMON_MEASUREMENT_CHARACTERISTIC:
            measurement_variable = characteristic[0]
            measurement_value = row[measurement_variable]
            measurement_named_individual = characteristic[1]
            if (pd.isnull(measurement_value)):
                pass
            else:
                observation_uri = JUVOUT_RESOURCE[f"observation.{measurement_variable}.{id}"]
                p = RDF.type
                o = JUVOUT_ONT.Escapement_Observation
                graph.add((observation_uri, p, o))

                p = SOSA.hasMember
                graph.add((observation_collection_uri, p, observation_uri))

                if (~pd.isnull(run)):
                    p = FO.runType
                    o = SALMON_RUN_TYPE_NAMED_INDIVIDUALS[run]
                    graph.add((observation_uri, p, o))
               
                measurement_uri = JUVOUT_RESOURCE[f"measurement.{measurement_variable}.{id}"]
                p = RDF.type
                o = JUVOUT_ONT.Escapement_Measurement
                graph.add((measurement_uri, p, o))
                # p = OBOE.measuresCharacteristic
                # o = JUVOUT_RESOURCE[f"salmonCharacteristic.JUVOUTIJ"]
                # graph.add((measurement_uri, p, o))

                p = OBOE.hasMeasurement
                graph.add((observation_uri, p, measurement_uri))

                # p = RDFS.label
                # o = Literal('Including jacks, point estimate for SAR or natural origin escapement for '+common_name+ ' made at '+ location_name + ' during '+ str(spawning_year) + "'s "+ run +'.', datatype=XSD.string)
                # graph.add((measurement_uri, p, o))

                p = FO.hasValue  
                try:
                    # Attempt to convert the string to an integer
                    int_value = int(measurement_value)
                    o = Literal(measurement_value, datatype=XSD.int)
                except ValueError:
                    try:
                        # Attempt to convert the string to a float
                        float_value = float(measurement_value)
                        o = Literal(measurement_value, datatype=XSD.float)
                    except ValueError:
                        o = Literal(measurement_value, datatype=XSD.string)

                # o = Literal(measurement_value, datatype=XSD.integer)
                graph.add((measurement_uri, p, o))

                p = SOSA.hasSimpleResult
                graph.add((observation_uri, p, o))

                p = OBOE.measuresCharacteristic
                o =  JUVOUT_ONT[measurement_named_individual]
                graph.add((measurement_uri, p, o))

                p = SOSA.observedProperty
                graph.add((observation_uri, p, o))

                p = STREAMNETONT.usesEstimationMethod
                graph.add((observation_uri, p, method_uri))
        
        #add metadata
        dataset_name = "JuvOut"
        description = "For natural origin fish this is the number of fish passing a defined point as they migrate downstream."
        title = "Juvenile Outmigrants (JuvOut)"

        dataset_uri = OBOE[f"dataset.{dataset_name}"]
        p = RDF.type
        o = OBOE.Dataset
        graph.add((dataset_uri, p, o))
        p = PROV.wasDerivedFrom
        graph.add((observation_collection_uri, p, dataset_uri))

        p = OBOE.description
        o = Literal(description, datatype=XSD.string)
        graph.add((dataset_uri, p, o))

        p = OBOE.title
        o = Literal(title, datatype=XSD.string)
        graph.add((dataset_uri, p, o))
           

    return graph

if __name__ == "__main__":

    df = pd.read_csv("../datasets/streamnet-cai/Streamnet_JUVOUT.csv", header=0, encoding='latin-1')
    output_folder = "output"

    os.makedirs(output_folder, exist_ok=True)

    graph = graphify(df)
    destination = os.path.join(output_folder, f"streamnet_juvout-dataset.ttl")
    for prefix in _PREFIX:
        graph.bind(prefix, _PREFIX[prefix])
    graph.serialize(destination=destination, format="ttl")
    print(f"Finished writing RDF information to {output_folder}...")




