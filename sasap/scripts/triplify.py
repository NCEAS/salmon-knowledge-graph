import re
import argparse
import os

import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, TIME, XSD, SOSA, ORG
from rdflib.namespace import DefinedNamespace
from rdflib.namespace._GEO import GEO
from shapely.geometry import Point
from shapely import box



FIRST_VARIABLE = "TotalPatients"

SB_BOUNDING_BOX = box(-120.734382, 33.411024, -118.962728, 35.114678)

KWG_ENDPOINT = "http://stko-kwg.geog.ucsb.edu/"

KWGR = Namespace(f"{KWG_ENDPOINT}lod/resource/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("https://qudt.org/vocab/unit/")

class KWG_ONT(DefinedNamespace):
    """a shortcut namespace with some enumerated classes/predicates used
    in this script
    """
    # Classes
    BPHC_Site: URIRef
    FederallyQualifiedHealthCenter: URIRef
    FQHC_ObservationCollection: URIRef
    FQHC_Observation: URIRef

    # Object properties
    hasBPHCSiteType: URIRef
    bphcSiteLocationType: URIRef

    # Data properties
    fqhcID: URIRef
    stateCode: URIRef
    bphcSiteID: URIRef
    bphcSiteName: URIRef
    hasWebpageURL: URIRef
    hasTelephoneNumber: URIRef

    _NS = Namespace(f"{KWG_ENDPOINT}lod/ontology/")


_PREFIX = {
    "kwgr": KWGR,
    "kwg-ont": KWG_ONT._NS,
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
    "qudt": QUDT,
    "unit": UNIT,
    "dcterms": DCTERMS,
    "addr": Namespace("https://spec.edmcouncil.org/fibo/ontology/FND/Places/Addresses/")
}

def camel_case(s: str) -> str:
    # Use regular expression substitution to replace underscores and hyphens with spaces,
    # then title case the string (capitalize the first letter of each word), and remove spaces
    s = re.sub(r"(_|-)+", " ", s).title().replace(" ", "")
    
    # Join the string, ensuring the first letter is lowercase
    return ''.join([s[0].lower(), s[1:]])


def graphify_row(row: pd.Series, idx_first_variable: int) -> Graph:
    graph = Graph()

    bphc_id = row["BPHC Assigned Number"]
    bpch_site_iri = KWGR[f"bphcSite.{bphc_id}"]
    p = RDF.type
    o = KWG_ONT.BPHC_Site
    graph.add((bpch_site_iri, p, o))

    label = f"Bureau of Primary Health Care (BPHC) site with ID {bphc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((bpch_site_iri, p, o))

    p = KWG_ONT.bphcSiteID
    o = Literal(bphc_id, datatype=XSD.string)
    graph.add((bpch_site_iri, p, o))

    bphc_site_name = row["Site Name"]
    p = KWG_ONT.bphcSiteName
    o = Literal(bphc_site_name, datatype=XSD.string)
    graph.add((bpch_site_iri, p, o))

    url = row["Site Web Address"]
    p = KWG_ONT.hasWebpageURL
    o = Literal(url, datatype=XSD.anyURI)
    graph.add((bpch_site_iri, p, o))

    address_iri = KWGR[f"address.bphcSite.{bphc_id}"]
    p = _PREFIX["addr"]["hasAddress"]
    graph.add((bpch_site_iri, p, address_iri))

    p = RDF.type
    o = _PREFIX["addr"]["Address"]
    graph.add((address_iri, p, o))

    label = f"Address of BPHC site with ID {bphc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((address_iri, p, o))

    address_line_1 = row["Site Address"]
    p = _PREFIX["addr"]["hasAddressLine1"]
    o = Literal(address_line_1, datatype=XSD.string)
    graph.add((address_iri, p, o))

    city_name = row["Site City"]
    p = _PREFIX["addr"]["hasCityName"]
    o = Literal(city_name, datatype=XSD.string)
    graph.add((address_iri, p, o))

    state_code = row["Site State Abbreviation"]
    p = KWG_ONT.stateCode
    o = Literal(state_code, datatype=XSD.string)
    graph.add((address_iri, p, o))

    postal_code = row["Site Postal Code"]
    p = _PREFIX["addr"]["hasPostalCode"]
    o = Literal(postal_code, datatype=XSD.string)
    graph.add((address_iri, p, o))

    telephone_number = row["Site Telephone Number"]
    p = KWG_ONT.hasTelephoneNumber
    o = Literal(telephone_number, datatype=XSD.string)
    graph.add((address_iri, p, o))

    location_type_str = camel_case(row["Health Center Location Type Description"])
    location_type_iri = KWGR[f"bphcSiteLocationType.{location_type_str}"]
    p = KWG_ONT.bphcSiteLocationType
    graph.add((bpch_site_iri, p, location_type_iri))

    site_type_str = row["Health Center Type Description"]
    p = KWG_ONT.hasBPHCSiteType
    if "Administrative" in site_type_str:
        site_type_iri = KWGR[f"bpchSiteType.administrative"]
        graph.add((bpch_site_iri, p, site_type_iri))
    if "Delivery" in site_type_str:
        site_type_iri = KWGR[f"bphcSiteType.serviceDeliverySite"]
        graph.add((bpch_site_iri, p, site_type_iri))

    lat = row["Latitude"]
    long = row["Longitude"]
    geometry = Point(long, lat)
    geom_type = geometry.geom_type
    geometry_iri = KWGR[f"geometry.{geom_type}.bpchSite.{bphc_id}"]
    p = GEO.hasGeometry
    graph.add((bpch_site_iri, p, geometry_iri))

    p = _PREFIX["geo"]["hasDefaultGeometry"]
    graph.add((bpch_site_iri, p, geometry_iri))

    p = RDF.type
    o = GEO.Geometry
    graph.add((geometry_iri, p, o))

    o = _PREFIX["sf"][geom_type]
    graph.add((geometry_iri, p, o))

    label = f"Geometry of BPHC site with ID {bphc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((geometry_iri, p, o))

    wkt = geometry.wkt
    p = GEO.asWKT
    o = Literal(wkt, datatype=GEO.wktLiteral)
    graph.add((geometry_iri, p, o))


    fqhc_id = row["Health Center Number"]
    fqhc_iri = KWGR[f"federallyQualifiedHealthCenter.{fqhc_id}"]
    p = ORG.hasSite
    graph.add((fqhc_iri, p, bpch_site_iri))

    p = RDF.type
    o = KWG_ONT.FederallyQualifiedHealthCenter
    graph.add((fqhc_iri, p, o))

    label = f"Federally Qualified Health Center with number {fqhc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((fqhc_iri, p, o))

    p = KWG_ONT.fqhcID
    o = Literal(fqhc_id, datatype=XSD.string)
    graph.add((fqhc_iri, p, o))

    address_iri = KWGR[f"address.federallyQualifiedHealthCenter.{fqhc_id}"]
    p = _PREFIX["addr"]["hasAddress"]
    graph.add((fqhc_iri, p, address_iri))

    p = RDF.type
    o = _PREFIX["addr"]["Address"]
    graph.add((address_iri, p, o))

    label = f"Address of Federally Qualified Health Center with number {fqhc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((address_iri, p, o))

    address_line_1 = row["Health Center Organization Street Address"]
    p = _PREFIX["addr"]["hasAddressLine1"]
    o = Literal(address_line_1, datatype=XSD.string)
    graph.add((address_iri, p, o))

    city_name = row["Health Center Organization City"]
    p = _PREFIX["addr"]["hasCityName"]
    o = Literal(city_name, datatype=XSD.string)
    graph.add((address_iri, p, o))

    state_code = row["Health Center Organization State"]
    p = KWG_ONT.stateCode
    o = Literal(state_code, datatype=XSD.string)
    graph.add((address_iri, p, o))

    postal_code = row["Health Center Organization ZIP Code"]
    p = _PREFIX["addr"]["hasPostalCode"]
    o = Literal(postal_code, datatype=XSD.string)
    graph.add((address_iri, p, o))

    collection_iri = KWGR[f"fqhcObservationCollection.{fqhc_id}"]
    p = SOSA.isFeatureOfInterestOf
    graph.add((fqhc_iri, p, collection_iri))

    p = RDF.type
    o = KWG_ONT.FQHC_ObservationCollection
    graph.add((collection_iri, p, o))

    label = f"Observation collection for Federally Qualified Health Center with number {fqhc_id}"
    p = RDFS.label
    o = Literal(label, datatype=XSD.string)
    graph.add((collection_iri, p, o))

    time_iri = KWGR["instant.2022"]
    p = SOSA.phenomenonTime
    graph.add((collection_iri, p, time_iri))

    for column_name in df.columns[idx_first_variable:-2]:
        value = row[column_name]
        if value != ' ':
            observation_iri = KWGR[f"fqhcObservation.{fqhc_id}.{column_name}"]
            p = _PREFIX["sosa"]["hasMember"]
            graph.add((collection_iri, p, observation_iri))

            p = RDF.type
            o = KWG_ONT.FQHC_Observation
            graph.add((observation_iri, p, o))

            label = f"Observation of the property {column_name} for the FQHC with number {fqhc_id}"
            p = RDFS.label
            o = Literal(label, datatype=XSD.string)
            graph.add((observation_iri, p, o))

            p = SOSA.observedProperty
            property_iri = KWGR[f"fqhcObservableProperty.{column_name}"]
            graph.add((observation_iri, p, property_iri))
            
            if value.is_integer():
                value = int(value)
                dtype = XSD.integer
            else:
                dtype = XSD.decimal

            p = SOSA.hasSimpleResult
            o = Literal(value, datatype=dtype)
            graph.add((observation_iri, p, o))

    return graph

    


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", action="store_true", help="filter the output to Santa Barbara")
    args = parser.parse_args()
    is_sb = args.sb

    df = pd.read_excel("FQHC_LAL_AllSites_Variables.xlsx")

    idx_first_variable = df.columns.get_loc(FIRST_VARIABLE)

    if is_sb:
        output_folder = "santa_barbara"
        print("Santa barbara filter is on...")
    else:
        output_folder = "output"

    os.makedirs(output_folder, exist_ok=True)

    for idx, row in df.iterrows():
        if is_sb:
            lat = row["Latitude"]
            long = row["Longitude"]
            geometry = Point(long, lat)
            if not geometry.intersects(SB_BOUNDING_BOX):
                continue
        file_name = str(idx) + ".ttl"
        destination = os.path.join(output_folder, file_name)
        graph = graphify_row(row, idx_first_variable)
        for prefix in _PREFIX:
            graph.bind(prefix, _PREFIX[prefix])
        graph.serialize(destination=destination, format="ttl")






