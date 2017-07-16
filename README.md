# OpenElections Data Arkansas

Converted CSVs of Arkansas election results that are provided in PDF.

This includes results for the following elections:

* [2002 General](http://www.sos.arkansas.gov/elections/historicalElectionResults/Documents/2002_General.pdf) (November 5, 2002)
* [2002 Preferential Primary & Non-Partisan Judicial](http://www.sos.arkansas.gov/elections/historicalElectionResults/Documents/2002_Preferential_Primary_Non-Partisan_Judicial.pdf) (May 21, 2002)
* [2002 Preferential Primary Run-off ](http://www.sos.arkansas.gov/elections/historicalElectionResults/Documents/2002_Preferential_Primary_Run-off.pdf) (June 11, 2002)

# Converting the PDFs

The PDF results were converted by first converting the PDF to text and passing
the text through a filter script that outputs CSV.

```
pdftotext -layout ~/workspace/openelex-core/openelex/us/ar/cache/20021105__ar__general.pdf - | ./scripts/parse_ar_general_pdf.py > 20021105__ar__general.csv
pdftotext -layout ~/workspace/openelex-core/openelex/us/ar/cache/20020521__ar__primary.pdf - | ./scripts/parse_ar_primary_pdf.py > 20020521__ar__primary.csv 
pdftotext -layout ~/workspace/openelex-core/openelex/us/ar/cache/20020611__ar__primary_runoff.pdf - | ./scripts/parse_ar_primary_pdf.py > 20020611__ar__primary_runoff.csv 
```

# Unicode Replacement

To make consumption a bit easier, we output the CSV in ASCII.  The general election results file has a few Unicode characters in the precinct names.  We replace them with ASCII characters as follows:

* "EN DASH" (U+2013) is converted to '-'
* "EM DASH" (U+2014) is converted to '-'
* "RIGHT SINGLE QUOTATION MARK" (U+2019) is converted to "'"


# Converted 2016 Clarify Election Results 

http://results.enr.clarityelections.com/AR/Arkansas/63914/184003/Web01/en/summary.html#


