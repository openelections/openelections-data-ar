#!/usr/bin/env python3

import clarify
import clarify.jurisdiction
import sys
import csv
import re
import requests
import zipfile
import shutil
import pandas as pd


### Getting Functions

# using the summary url, downloads all the detail xml files , unzips them, 
# renames the detail to prefix_county.xml
def get_county_files(c_url, prefix):
    
    # state should be here, not county (in 2016)
    jurisdiction = clarify.Jurisdiction(url=c_url, level='state')

    for j in jurisdiction.get_subjurisdictions():
        print("County: ", j.name, j.report_url('xml'))
        
        if j.report_url('xml'):
            detail_url = j.report_url('xml').replace("http:", "https:")
            r = requests.get(detail_url, allow_redirects=True)
            zip_filename = j.name + "_detailxml.zip"
            open(zip_filename, 'wb').write(r.content)
            zip = zipfile.ZipFile(zip_filename)
            zip.extractall()
            shutil.move("detail.xml", prefix + j.name + ".xml")


### Processing Functions

# Extract vote totals one for one subjurisdiction (precinct)
def buildLine(county, r):

  district = ""
  precinct = r.jurisdiction

  hand_count = 0
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

  # Can be Early Vote, Early Vote (North), Early Vote (South)
  # could be Early Vote or Early Voting
  # vote types in the primary file

  # Absentee
  # Counted Provisional
  # Early Vote
  # Early Vote - HSB
  # Early Vote Ivo Machine
  # Early Vote - North
  # Early Vote - Ozarka
  # Early Vote Paper
  # Early Vote - South
  # Early Voting
  # Election Day
  # Election Day Ivo Machine \#
  # Election Day Paper
  # Election Night
  # Hand Count
  # Manual \#
  # Provisional

  if (vote_type.startswith("Early Vot")) | (vote_type == "Early Voting") | (vote_type.startswith("Early Day")):
    early_vote = votes
  elif (vote_type.startswith('Election Day') | (vote_type == "Election Night")):
    election_day = votes
  elif (vote_type.startswith('Absentee')) | (vote_type.startswith('ABSENTEE')):
    absentee = votes 
  elif (vote_type.startswith('Provisional') | (vote_type == "Counted Provisional")):
    provisional = votes
  elif (vote_type.startswith('Hand Count')) | (vote_type.startswith('Manual')):
    hand_count = votes
  ### SPECIFICALLY TO FIX DeRouche and El Paso oddity in Nov 2014
  elif (vote_type.startswith('DeRouche')) | (vote_type.startswith('El Paso')):
  	if(vote_type.startswith('DeRouche')):
  		precinct = 'DeRoche'
  	if(vote_type.startswith('El Paso')):
  		precinct = "EL PASO"
  	election_day = votes
  else:
    print("WARNING VOTE TYPE ", vote_type, votes)
    other = votes

  item = {'county': county, 'precinct': precinct, 'office': office, 'district': district,
    'party': party, 'candidate': candidate, 'votes': votes, 
    'vote_type': vote_type, 'early_vote': early_vote, 'absentee': absentee, 'election_day': election_day,
    'provisional': provisional, 'hand_count': hand_count }

  return(item)

# Given filename, will return list of items
def extract_data_from_file(filename):
    items = []
    p = clarify.Parser()
    p.parse(filename)
    print( "Processing ", filename, p.election_name, p.region )
    county = p.region

    for r in p.results:
        if r.votes > 0:
            if r.choice is not None:
                # This is called to build a line from results
                item = buildLine(county, r)
                if item is not None:
                    items.append( item )

    return(items)

# Given items, will roll up total votes, returns rolled up items
def rollup_by_vote_type(items):
  df = pd.DataFrame.from_dict(items)
  grp = df.groupby(['county', 'precinct', 'office', 'district', 'party', 'candidate'])
  grouped_items = []
  
  for k, gg in grp:
    votes = sum(gg['votes'])
    election_day = sum(gg['election_day'])
    early_vote = sum(gg['early_vote'])
    absentee = sum(gg['absentee'])
    provisional = sum(gg['provisional'])
    hand_count = sum(gg['hand_count'])

    gitem = ( str(k[0]), str(k[1]), str(k[2]), str(k[3]), str(k[4]), str(k[5]),
      str(int(votes)), str(int(election_day)), str(int(early_vote)),
      str(int(absentee)), str(int(provisional)), str(int(hand_count)) )

    if votes != (election_day + early_vote + absentee + provisional + hand_count):
      print("VOTE ISSUE", votes, election_day, early_vote, absentee, provisional, hand_count, gitem )

    grouped_items = grouped_items + list([gitem])

  return(grouped_items)

def output_file(outfile,items):
  "write items to file"
  with open(outfile, "w") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'precinct', 'office', 'district',
                      'party', 'candidate', 'votes', 'election_day', 
                      'early_vote', 'absentee', 'provisional', 'hand_count'])
    outfile.writerows(items)


# Data files must be prefected and named <prefix><county>.xml
# Processes each file, extracts vote totals, rolls up by vote type,
# and returns a list of items
def process_county_files(c_url, outfile, prefix):

    # Should be state, not county
    jurisdiction = clarify.Jurisdiction(url=c_url, level='state')
    
    allitems = []
    allcandidates = []
    for j in jurisdiction.get_subjurisdictions():
        county = j.name
        if j is not None:
            try:
                if j.report_url('xml'):
                    filename = prefix + j.name + ".xml"
                    # Calls Helper Functions
                    items = extract_data_from_file(filename)
                    grouped_items = rollup_by_vote_type(items)
                    allitems = allitems + grouped_items
                    
            except Exception as ex:
                print("FAILED: Processing ", county, filename, j.report_url('xml'))
                if hasattr(ex, 'message'):
                    print(ex.message)
                else:
                    print(ex)

    output_file(outfile, allitems)


### Debugging Functions

# For testing/debugging - handle one xml file
def process_single_file(filename):
    items = extract_data_from_file(filename)
    gitems = rollup_by_vote_type(items)
    print("Num items", len(items), " num gitems ", len(gitems))
    output_file("single.csv", gitems)

# For testing/debugging - print vote types
def print_vote_types(items):
    df = pd.DataFrame.from_dict(items)
    print(items[0])

    vt_grp = df.groupby(['vote_type'])
    for v, vg in vt_grp:
        print("print_vote_types: ", v)



###############################################################################

def usage():
  print("usage: parser [fetch|process] [march2016|nov2016]")

pres_election_2014_url = "https://results.enr.clarityelections.com/AR/53237/149792/Web01/en/summary.html"
pres_election_file =     "20141104__ar__general__precinct.csv"

primary_election_may_2014_url = "https://results.enr.clarityelections.com/AR/51266/133405/en/summary.html"
primary_election_may_2014_file = "20140520__ar__primary__precinct.csv"

primary_eleciton_june_2014_url = "http://results.enr.clarityelections.com/AR/51821/134305/en/select-county.html"
primary_election_june_2014_file = "20140610__ar__primary__precinct.csv"


if __name__ == "__main__":
  if len(sys.argv) != 3:
    usage()
    sys.exit(1)

  cmd = sys.argv[1]
  which = sys.argv[2]
  if cmd == "fetch":
    if which == "may2014":
      print("Getting PRIMARY files")
      get_county_files(primary_election_may_2014_url, "may2014_")
    elif which == "june2014":
      print("Getting PRIMARY RUNOFF files")
      get_county_files(primary_eleciton_june_2014_url, "june2014_")
    elif which == "nov2014":
      print("Getting General election files")
      get_county_files(pres_election_2014_url, "nov2014_")
    else:
      usage()
  elif cmd == "process":
    if which == "may2014":
      print("Processsing PRIMARY files")
      process_county_files(primary_election_may_2014_url, primary_election_may_2014_file, "may2014_")
    elif which == "june2014":
      print("Processsing PRIMARY files")
      process_county_files(primary_eleciton_june_2014_url, primary_election_june_2014_file, "june2014_")
    elif which == "nov2014":
      print("Processsing General Election files")
      process_county_files(pres_election_2014_url, pres_election_file, "nov2014_")
    else:
      usage()
