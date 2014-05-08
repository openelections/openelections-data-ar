#!/usr/bin/env python

import re

from base import ParserState, BaseParser, LegendState, get_arg_parser, parse_csv
from util import parse_date

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


class CountyState(ParserState):
    county_re = re.compile(r'^[a-zA-Z ]+ County$')

    def __init__(self, context):
        super(CountyState, self).__init__(context)
        self._skip = False

    def handle_line(self, line):
        if self.county_re.match(line) and not self._skip:
            self._context.set('county', line)
            self._context.set('parent', self.name)
            self._context.change_state('county_results')
        elif line.endswith("Non Partisan Judicial"):
            self._skip = True
        elif line.endswith("Republican"):
            self._skip = False
            self._context.set('party', 'Republican')
        elif line.endswith("Democrat"):
            self._skip = False
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

    def __init__(self, context):
        super(CountyResultsState, self).__init__(context)
        self._nonblank_re = re.compile(r'\w+')

    def handle_line(self, line):
        if line == "Election Statistics": 
            self._context.change_state('election_statistics')
        elif self._nonblank_re.match(line):
            self._context.set('office', line)
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
            if "Total under votes" in line:
                self._context.unset('office')
                self._context.change_state('county_results')

    def parse_result(self, line):
        bits = re.split(r'\s+', line)
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
        self._context.unset('legend')

    def parse_result(self, line):
        legend = self._context.get('legend')
        bits = re.split(r'\s+', line)
        # Sometimes zeros aren't split
        if bits[-1] == "0000":
            precinct = ' '.join(bits[:-1])
            votes = ['0', '0', '0', '0']
        elif bits[-1] == "000":
            precinct = ' '.join(bits[:-2])
            votes = [bits[-1], '0', '0', '0']
        else:
            precinct = ' '.join(bits[:-len(legend)])
            votes = bits[-len(legend):]

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


class ResultParser(BaseParser):
    def __init__(self, infile):
        super(ResultParser, self).__init__(infile)
        self._register_state(RootState(self))
        self._register_state(CountySummariesState(self))
        self._register_state(CertificationReport(self))
        self._register_state(CountyResultsState(self))
        self._register_state(ElectionStatisticsState(self))
        self._register_state(ContestResultsState(self))
        self._register_state(LegendState(self))
        self._register_state(PrecinctResultsState(self))
        self._current_state = self._get_state('root')
        self.set('seen_summaries', False)


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
