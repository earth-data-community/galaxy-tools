#!/usr/bin/env python3
#
#
# usage: wfs_download.py [-h] [--format FORMAT] [--output OUTPUT] [-v]
#               url version typename
#
# positional arguments:
#  url              Specify url for WFS service
#  version          Specify which version to use for WFS services
#                   (1.0.0, 1.1.0, 2.0.0, 3.0.0)
#  typename         Feature Type name to retrieve
#
# optional arguments:
#  -h, --help       show this help message and exit
#  --format FORMAT  Specify the output format (csv, geojson, gml, etc.)
#  --output OUTPUT  output filename to store retrieved data
#  --max MAXLINES   Maximum number of features to retrieve
#  -v, --verbose    switch on verbose mode
#

import argparse
import warnings
from pathlib import Path

from owslib.wfs import WebFeatureService


class WFSservices ():
    def __init__(self, url, version, typename, format, output, maxlines,
                 verbose=False
                 ):
        self.url = url
        self.version = version
        self.typename = typename
        if format is None:
            self.format = 'geojson'
        else:
            self.format = format
        if output is None:
            self.output = Path(input).stem + '.' + self.format
        else:
            self.output = output + '.' + self.format
        if maxlines is None:
            self.maxlines = ''
        else:
            self.maxlines = maxlines

        self.verbose = verbose
        if verbose:
            print("url: ", self.url)
            print("version: ", self.version)
            print("typename: ", self.typename)
            print("format: ", self.format)
            print("output: ", self.output)
            print("maxlines: ", self.maxlines)
            print("verbose: ", self.verbose)

    def save(self):
        wfs = WebFeatureService(url=self.url, version=self.version)
        # check that typename is in the list of available feature types
        try:
            idx = list(wfs.contents).index(self.typename)
        except ValueError:
            idx = -1
            print("Invalid typename " + self.typename + ' with WFS service ' + self.url)

        if idx >= 0:
            response = wfs.getfeature(typename=self.typename,
                                      outputFormat=self.format)
            if self.maxlines != '' and self.format == 'csv':
                ans = ""
                for i in range(int(self.maxlines)):
                    ans += response.readline()
            else:
                ans = ''.join(response.readlines())

            out = open(self.output, 'wb')
            out.write(bytes(ans.encode('utf-8', 'ignore')))
            out.close()


def retrieve_wfs(url, version, typename, format, output, maxlines, verbose):
    """Retrieve all data from WFS service"""

    p = WFSservices(url, version, typename, format, output, maxlines, verbose)
    p.save()


if __name__ == '__main__':
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'url',
        help='Specify url for WFS service'
    )
    parser.add_argument(
        'version',
        help='Specify which version to use for WFS services (1.0.0, ...)'
    )
    parser.add_argument(
        'typename',
        help='Feature Type name to retrieve'
    )

    parser.add_argument(
        '--format',
        help='Specify the output format (csv, geojson, gml, etc.)'
    )
    parser.add_argument(
        '--output',
        help='output filename to store retrieved data'
    )
    parser.add_argument(
        '--max',
        help='Maximum number of features to retrieve'
    )
    parser.add_argument(
        "-v", "--verbose", help="switch on verbose mode",
        action="store_true")
    args = parser.parse_args()

    retrieve_wfs(args.url, args.version, args.typename, args.format,
                 args.output, args.max, args.verbose)
