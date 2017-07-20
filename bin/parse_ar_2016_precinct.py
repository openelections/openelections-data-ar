#!/usr/bin/env python3

import os.path
import clarify
import clarify.jurisdiction
import csv
import re
import requests
import zipfile
import shutil
import pandas as pd
from collections import OrderedDict

# extract vote totals one subjurisdiction
def buildLine(county, r):
  district = ""
  precinct = r.jurisdiction

  total_votes = 0
  early_vote = 0
  election_day = 0
  provisional = 0
  absentee = 0

  party = "unknown party"
  candidate = "unknown candidate"
  office = r.contest.text
  office = office.replace('  ', ' ')
  parts = office.split(",")


  if len(parts) == 2:
    house = office.find( "House")
    senate = office.find( "Senate")
    if house >= 0 or senate >= 0:
      office = parts[0].strip()
      district = parts[1].strip()

  if r.jurisdiction is not None:
    precinct = r.jurisdiction.name

  if precinct is None:
    return None

  if r.choice is not None:
    total_votes = r.choice.total_votes
    votes = r.votes
    vote_type = r.vote_type
    party = r.choice.party
    candidate = r.choice.text
    candidate = candidate.replace('  ', ' ')

    if vote_type == 'Early Vote':
      early_vote = votes

    if vote_type == 'Election Day':
      election_day = votes

    if vote_type == 'Absentee':
      absentee = votes

    if vote_type == 'Provisional':
      provisional = votes

    item = {'county': county, 'precinct': precinct, 'office': office, 'district': district,
            'party': party, 'candidate': candidate, 'votes': votes, 
            'vote_type': vote_type, 'early_vote': early_vote, 'absentee': absentee, 'election_day': election_day,
            'provisional': provisional}
    return(item)


# write items to file
def output_file(outfile,items):
  with open(outfile, "w") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'precinct', 'office', 'district',
                      'party', 'candidate', 'votes', 'election_day', 'early_vote', 'absentee', 'provisional'])

    outfile.writerows(items)


# process a file and return list  of items
def extract_data_from_file(filename):

  items = []
  p = clarify.Parser()
  p.parse(filename)
  print( "Processing ", filename, p.election_name, p.region )
  county = p.region

  for r in p.results:
     if r.votes > 0:
       if r.choice is not None:
         item = buildLine(county, r)
         if item is not None:
           items.append( item )

  return(items)


# using the summary url, downloads all the detail xml files 
# named prefix_county.xml
def get_county_files(c_url, prefix):
  jurisdiction = clarify.Jurisdiction(url=c_url, level='county')

  for j in jurisdiction.get_subjurisdictions():
    print("j ", j.name, j.report_url('xml'))
    if j.report_url('xml'):
        detail_url = j.report_url('xml').replace("http:", "https:")
        r = requests.get(detail_url, allow_redirects=True)
        zip_filename = j.name + "_detailxml.zip"
        open(zip_filename, 'wb').write(r.content)
        zip = zipfile.ZipFile(zip_filename)
        zip.extractall()
        shutil.move("detail.xml", prefix + j.name + ".xml")


def process_county_files(c_url, outfile, prefix):
  jurisdiction = clarify.Jurisdiction(url=c_url, level='county')
  allitems = []
  for j in jurisdiction.get_subjurisdictions():
    county = j.name
    try:
      if j.report_url('xml'):
        filename = prefix + j.name + ".xml"
        items = extract_data_from_file(filename)
        df = pd.DataFrame.from_dict(items)
        grp = df.groupby(['county', 'precinct', 'office', 'district', 'party', 'candidate'])


        grouped_items = []
        for k, g in grp:

            gg = grp.get_group(k)
            votes = sum(gg['votes'])
            election_day = sum(gg['election_day'])
            early_vote = sum(gg['early_vote'])
            absentee = sum(gg['absentee'])
            provisional = sum(gg['provisional'])

            gitem = (
                k[0], k[1], k[2], str(k[3]), str(k[4]), str(k[5]),
                      str(int(votes)),
                      str(int(election_day)),
                      str(int(early_vote)),
                      str(int(absentee)),
                      str(int(provisional)))


            grouped_items = grouped_items + list([gitem])

        allitems = allitems + grouped_items
    except:
        print("FAILED: Processing ", county, filename, j.report_url('xml'))
        #print("Unexpected error:", sys.exec_info()[0])

  output_file(outfile,allitems)

###############################################################################

pres_election_2016_url = "https://results.enr.clarityelections.com/AR/63912/184685/Web01/en/summary.html"
pres_election_file =     "20161108__ar__general__precinct.csv"

primary_election_march_2016_url = "http://results.enr.clarityelections.com/AR/58350/163701/Web01/en/summary.html"
primary_election_march_2016_file = "20160301__ar__primary__precinct.csv"

#get_county_files(pres_election_2016_url, "nov2016_")
#process_county_files(pres_election_2016_url, pres_election_file, "nov2016_")

#get_county_files(primary_election_march_2016_url, "mar2016_")
process_county_files(primary_election_march_2016_url, primary_election_march_2016_file, "mar2016_")

