#!/usr/bin/env python

import clarify
import clarify.jurisdiction
import sys
import csv
import re
import requests
import zipfile
import shutil
import pandas as pd

def buildLine(county, r):
  "extract vote totals one for one subjurisdiction (precinct)"

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

    # Martin O'Mally appears with 2 different spellings
    if candidate == "Martin J O'Malley":
      candidate = "Martin J. O'Malley"

    # Can be Early Vote, Early Vote (North), Early Vote (South)
    # could be Early Vote or Early Voting

    """
    vote types in the primary file

    Absentee
    Counted Provisional
    Early Vote
    Early Vote - HSB
    Early Vote Ivo Machine
    Early Vote - North
    Early Vote - Ozarka
    Early Vote Paper
    Early Vote - South
    Early Voting
    Election Day
    Election Day Ivo Machine
    Election Day Paper
    Election Night
    Hand Count
    Provisional
    """

    if (vote_type.startswith("Early Vot")) | (vote_type == "Early Voting"):
      early_vote = votes
    elif (vote_type.startswith('Election Day') | (vote_type == "Election Night")):
      election_day = votes
    elif vote_type.startswith('Absentee'):
      absentee = votes
    elif (vote_type.startswith('Provisional') | (vote_type == "Counted Provisional")):
      provisional = votes
    elif vote_type.startswith('Hand Count'):
      hand_count = votes
    else:
      print("WARNING VOTE TYPE ", vote_type, votes)
      other = votes

    item = {'county': county, 'precinct': precinct, 'office': office, 'district': district,
            'party': party, 'candidate': candidate, 'votes': votes,
            'vote_type': vote_type, 'early_vote': early_vote, 'absentee': absentee, 'election_day': election_day,
            'provisional': provisional, 'hand_count': hand_count }
    return(item)


def output_file(outfile,items):
  "write items to file"
  with open(outfile, "w") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'precinct', 'office', 'district',
                      'party', 'candidate', 'votes', 'election_day',
                      'early_vote', 'absentee', 'provisional', 'hand_count'])
    outfile.writerows(items)


def extract_data_from_file(filename):
  "process a file and return list  of items"

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


def get_county_files(c_url, prefix):
  """
  using the summary url, downloads all the detail xml files , unzips them,
  renames the detail to prefix_county.xml
  """
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

def print_vote_types(items):
  df = pd.DataFrame.from_dict(items)
  print(items[0])

  vt_grp = df.groupby(['vote_type'])
  for v, vg in vt_grp:
    print("print_vote_types: ", v)

def rollup_by_vote_type(items):
  "Rolls up votes and adds the election day, absentee, early voting, and provisional values to the item"

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


def process_county_files(c_url, outfile, prefix):
  """
  Data files must be prefected and named <prefix><county>.xml

  Processes each file, extracts vote totals, rolls up by vote type,
  and returns a list of items
  """
  jurisdiction = clarify.Jurisdiction(url=c_url, level='state')
  allitems = []
  for j in jurisdiction.get_subjurisdictions():
    county = j.name
    if j is not None:
      try:
        if j.report_url('xml'):
          filename = prefix + j.name + ".xml"
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


def process_single_file(filename):
  "for testing/debugging - handle one xml file"
  items = extract_data_from_file(filename)
  gitems = rollup_by_vote_type(items)
  print("Num items", len(items), " num gitems ", len(gitems))
  output_file("single.csv", gitems)

def usage():
  print("usage: parser [fetch|process] [march2016|nov2016]")

###############################################################################

pres_election_2016_url = "http://results.enr.clarityelections.com/AR/42843/113233/en/summary.html"
pres_election_file =     "20121106__ar__general__precinct.csv"

primary_election_march_2016_url = "http://results.enr.clarityelections.com/AR/39981/89122/en/summary.html"
primary_election_march_2016_file = "20120522__ar__primary__precinct.csv"

if __name__ == "__main__":
  if len(sys.argv) != 3:
    usage()
    sys.exit(1)

  cmd = sys.argv[1]
  which = sys.argv[2]
  if cmd == "fetch":
    if which == "march2016":
      print("Getting PRIMARY files")
      get_county_files(primary_election_march_2016_url, "mar2016_")
    elif which == "nov2016":
      print("Getting General election files")
      get_county_files(pres_election_2016_url, "nov2016_")
    else:
      usage()
  elif cmd == "process":
    if which == "march2016":
      print("Processsing PRIMARY files")
      process_county_files(primary_election_march_2016_url, primary_election_march_2016_file, "mar2016_")
    elif which == "nov2016":
      print("Processsing General Election files")
      process_county_files(pres_election_2016_url, pres_election_file, "nov2016_")
    else:
      usage()
