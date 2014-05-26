#!/usr/bin/env python

import re

from openelexdata.us.ar.base import ParserState, BaseParser, LegendState, get_arg_parser, parse_csv
from openelexdata.us.ar.util import parse_date

class RootState(ParserState):
    name = 'root'
    _date_re = re.compile(r'(May|June|November) \d{1,2}(th|), \d{4}')

    def handle_line(self, line):
        if self._date_re.match(line) and not self._context.has('date'):
            self._context.set('date', parse_date(line))
        elif line == "County Sumamry of Votes":
            self._context.change_state('county_summaries')
        elif (line == "Certification Report" and
              self._context.get('seen_summaries')):
            self._context.change_state('certification_report')
        elif line == "Vote totals for all candidates":
            self._context.change_state('vote_totals')


class VoteTotalsState(ParserState):
    name = 'vote_totals'

    def handle_line(self, line):
        if line == "All unopposed":
            self._context.change_state('judicial_all_unopposed')
        elif line != "":
            self._context.set('office', line)
            self._context.change_state('contest_totals')


class ContestTotalsState(ParserState):
    name = 'contest_totals'

    def handle_line(self, line):
        if line == "State of Arkansas" :
            self._context.change_state('root')
        elif line == "" and len(self._results) > 0:
            self._context.change_state('vote_totals')
        elif line == "":
            return
        else:
            self.parse_result(line)

    def enter(self):
        self._results = []

    def parse_result(self, line):
        bits = re.split(r'\s+', line)
        candidate = ' '.join(bits[:-2])
        candidate_bits = candidate.split(' - ')
        votes = bits[-2].replace(',', '')
        percentage = bits[-1].replace('%', '')
        name = candidate_bits[0].strip()
        party = candidate_bits[1].strip()
        if party == "Non Partisan Judicial":
            party = ""

        result = {
            'date': self._context.get('date'),
            'office': self._context.get('office'),
            'candidate': name,
            'party': party, 
            'reporting_level': 'contest',
            'jurisdiction': "Arkansas", 
            'votes': votes,
            'percentage': percentage,
        }
        self._results.append(result)
        self._context.results.append(result)


class JudicialAllUnopposedState(ParserState):
    name = 'judicial_all_unopposed'

    def handle_line(self, line):
        if line == "State of Arkansas" :
            self._context.change_state('root')


class CountyState(ParserState):
    county_re = re.compile(r'^[a-zA-Z ]+ County$')

    def handle_line(self, line):
        if self.county_re.match(line):
            self._context.set('county', line)
            self._context.set('parent', self.name)
            self._context.change_state('county_results')
        elif line.endswith("Non Partisan Judicial"):
            self._context.set('party', "")
        elif line.endswith("Republican"):
            self._context.set('party', 'Republican')
        elif line.endswith("Democrat"):
            self._context.set('party', 'Democrat')
        elif line == "State of Arkansas" :
            self._context.unset('party')
            self._context.unset('parent')
            self._context.change_state('root')


class CountySummariesState(CountyState):
    name = 'county_summaries'

    def exit(self):
        super(CountyState, self).exit()
        self._context.set('seen_summaries', True)


class CertificationReport(CountyState):
    name = 'certification_report'


class CountyResultsState(ParserState):
    name = 'county_results'
    _nonblank_re = re.compile(r'\w+')

    def handle_line(self, line):
        if line == "Election Statistics": 
            self._context.change_state('election_statistics')
        elif self._nonblank_re.match(line):
            office = line
            if " - " in office:
                office = office.split(" - ")[0]
            self._context.set('office', office)
            self._context.change_state('contest_results')


class ElectionStatisticsState(ParserState):
    name = 'election_statistics'

    def handle_line(self, line):
        if "Total number of unused ballots" in line:
            parent = self._context.get('parent')
            self._context.change_state(parent)


class ContestResultsState(ParserState):
    name = 'contest_results'

    def handle_line(self, line):
        if line == "":
            return
        elif line == "LEGEND":
            self._context.change_state('legend')
        elif self._context.has('legend'):
            self._context.change_state('precinct_results')
        else:
            self.parse_result(line)
            if "Total under votes" in line or "All unopposed" in line:
                self._context.unset('office')
                self._context.change_state('county_results')

    def parse_result(self, line):
        bits = re.split(r'\s+', line)
        if line.startswith("Total"):
            # Total over votes / Total under votes don't have a percentage
            percentage = ""
            votes = bits[-1]
            name = ' '.join(bits[:-1]).strip()
        else:
            percentage = bits[-1].replace('%', '')
            votes = bits[-2]
            name = ' '.join(bits[:-2]).strip()

        assert votes != ""

        result = {
            'date': self._context.get('date'),
            'office': self._context.get('office'),
            'candidate': name,
            'party': self._context.get('party'),
            'reporting_level': 'county',
            'jurisdiction': self._context.get('county'),
            'county': self._context.get('county'),
            'votes': votes,
            'percentage': percentage,
        }
        self._context.results.append(result)



class PrecinctResultsState(ParserState):
    name = 'precinct_results'
    _consecutive_zeros_re = re.compile(r'00+$')

    def handle_line(self, line):
        if line.startswith("1"):
            # Header row, e.g.
            # 1 2 3 4 5
            return
        elif line == "":
            self._context.change_state('county_results')
        else:
            self.parse_result(line)

    def exit(self):
        if self._context.has('inject_corrections'):
            county = self._context.get('county')
            self._context.inject_corrections(office=self._context.get('office'),
                reporting_level='precinct', county=county,
                legend=self._context.get('legend'),
                party=self._context.get('party'))

            self._context.unset('inject_corrections')

        self._context.unset('legend')

    def parse_result(self, line):
        legend = self._context.get('legend')
        bits = re.split(r'\s+', line)
        # Sometimes zeros aren't split
        if self._consecutive_zeros_re.match(bits[-1]):
            num_compacted = len(bits[-1])
            # Remove the last item and replace with individual '0' chars
            bits.pop()
            for i in range(num_compacted):
                bits.append('0')

        precinct = ' '.join(bits[:-len(legend)])
        votes = bits[-len(legend):]

        if not re.match(r'\d+', votes[0]):
            # There are some messed up lines.  Don't try to parse
            # and deal with them later.
            if (line.startswith("Dobson-Cooper") or 
                    line.startswith("Willis all Wards") or
                    line.startswith("Early & Absentee")):
                self._context.set('inject_corrections', True)
                return
            
            # Sometimes there are just missing votes
            precinct, votes = self._fix_votes(precinct, votes, legend)

        assert len(votes) == len(legend)

        for i in range(len(votes)):
            name = legend[i]

            result = {
                'date': self._context.get('date'),
                'office': self._context.get('office'),
                'candidate': name,
                'party': self._context.get('party'),
                'reporting_level': 'precinct',
                'jurisdiction': precinct, 
                'county': self._context.get('county'),
                'votes': votes[i].replace(',', ''),
            }
            self._context.results.append(result)

    def _fix_votes(self, precinct, votes, legend):
        precinct_bits = []
        if precinct:
            precinct_bits.append(precinct)
        clean_votes = []
        for vote in votes:
            if not re.match(r'\d+', vote):
                precinct_bits.append(vote)
            else:
                clean_votes.append(vote)

        while len(clean_votes) < len(legend):
            clean_votes.append('0')

        return ' '.join(precinct_bits), clean_votes


class ResultParser(BaseParser):
    def __init__(self, infile):
        super(ResultParser, self).__init__(infile)
        self._register_state(RootState(self))
        self._register_state(VoteTotalsState(self))
        self._register_state(ContestTotalsState(self))
        self._register_state(JudicialAllUnopposedState(self))
        self._register_state(CountySummariesState(self))
        self._register_state(CertificationReport(self))
        self._register_state(CountyResultsState(self))
        self._register_state(ElectionStatisticsState(self))
        self._register_state(ContestResultsState(self))
        self._register_state(LegendState(self))
        self._register_state(PrecinctResultsState(self))
        self._current_state = self._get_state('root')
        self.set('seen_summaries', False)

    def inject_corrections(self, office, reporting_level, county, legend,
            **kwargs):
        if (office == "Circuit Judge, District 02, Division 01, At Large" and
                reporting_level == 'precinct' and
                county == "Poinsett County"):
            party = kwargs.get('party')
            corrections = {
                "Little River - Payneway": [29, 44, 0, 0],
                "Lunsford - Weona & McCormick": [8, 17, 0, 9],
                "Lunsford-Tulot": [12, 17, 0, 0],
                "Owen-Fisher City & Rural": [44, 22, 0, 11],
                "Owen-Waldenburg City & Rural": [21, 38, 0, 0],
                "Tyronza City & Rural": [82, 109, 3, 30],
                "Scott-Valley View": [50, 24, 0, 0],
                "Scott-Whitehall": [24, 31, 0, 0],
                "Dobson-Cooper Haynes West Prairie City & Rural": [96, 102, 0, 22],
                "Willis all Wards & Twp": [444, 587, 5, 59],
                "Early & Absentee": [102, 181, 1, 36],
            }
            for jurisdiction, votes in corrections:
                for i in range(len(legend)):
                    name = legend[i]
                    self.results.append({
                        'date': self.get('date'),
                        'office': office,
                        'candidate': name,
                        'party': party, 
                        'reporting_level': 'precinct',
                        'jurisdiction': jurisdiction, 
                        'county': county,
                        'votes': "{}".format(votes[i]),
                    })


fields = [
    'date',
    'office',
    'candidate',
    'party',
    'reporting_level',
    'jurisdiction',
    'county',
    'votes',
    'percentage',
]


if __name__ == "__main__":
    args = get_arg_parser().parse_args()
    parse_csv(args.infile, args.outfile, fields, ResultParser)
