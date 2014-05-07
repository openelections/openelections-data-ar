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
pdftotext -layout /path/to/openelex-core/openelex/us/ar/cache/20020521__ar__primary.pdf - | ./scripts/parse_ar_primary_pdf.py > 20020521__ar__primary.csv
```
