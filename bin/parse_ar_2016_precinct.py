import clarify
import clarify.jurisdiction
import csv
import re
import requests
import zipfile
import shutil


# extract vote totals one subjurisdiction
def buildLine(county,r):
  district = ""
  precinct = r.jurisdiction

  total_votes = 0
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

  if r.choice is not None:
    total_votes = r.choice.total_votes
    votes = r.votes
    party = r.choice.party
    candidate = r.choice.text
    candidate = candidate.replace('  ', ' ')

  if precinct is None:
    return None
  else:
    return([county, precinct, office, district, party, candidate, votes])

# write items to file
def output_file(outfile,items):
  with open(outfile, "w") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes'])
    outfile.writerows(items)


# process a file and return list  of items
def go(filename):

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

# process a file and return list  of items
def processCounties(counties,outfile):
  allitems = []
  for c in counties:
    print( "Processing county: ", c )

    infile = c + ".xml"
    items = go(infile)
    allitems = allitems + items
    print( "      Num items in ", c, " = ", len(items))


  print( "processed ", len(counties), " counties" )
  print( "total items ", len(allitems))
  output_file(outfile, allitems)


def get_county_files():
  c_url = "http://results.enr.clarityelections.com/AR/58350/163701/Web01/en/summary.html"
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
        shutil.move("detail.xml", j.name + ".xml")

def process_county_files():
  c_url = "http://results.enr.clarityelections.com/AR/58350/163701/Web01/en/summary.html"
  jurisdiction = clarify.Jurisdiction(url=c_url, level='county')
  allitems = []
  for j in jurisdiction.get_subjurisdictions():
    print("j ", j.name, j.report_url('xml'))
    if j.report_url('xml'):
        filename = j.name + ".xml"
        items = go(filename)
        allitems = allitems + items

  outfile = "20160301__ar__primary__precinct.csv"
  output_file(outfile,allitems)

# download the files first, so no need to redownload if there are parser errors
#get_county_files()
process_county_files()
