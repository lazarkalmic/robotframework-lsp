# Original work Copyright 2008-2015 Nokia Networks
# Original work Copyright 2016-2020 Robot Framework Foundation
# See ThirdPartyNotices.txt in the project root for license information.
# All modifications Copyright (c) Robocorp Technologies Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http: // www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET


class Tags(object):
    def __init__(self, tags=None):
        self.tags = tags


class LibraryDoc(object):
    def __init__(
        self,
        name="",
        doc="",
        version="",
        type="library",
        scope="",
        named_args=True,
        doc_format="",
    ):
        self.name = name
        self.doc = doc
        self.version = version
        self.type = type
        self.scope = scope
        self.named_args = named_args
        self.doc_format = doc_format or "ROBOT"
        self.inits = []
        self.keywords = []

    @property
    def doc_format(self):
        return self._doc_format

    @doc_format.setter
    def doc_format(self, doc_format):
        self._doc_format = doc_format or "ROBOT"

    @property
    def keywords(self):
        return self._keywords

    @keywords.setter
    def keywords(self, kws):
        self._keywords = sorted(kws, key=lambda kw: kw.name)

    @property
    def all_tags(self):
        from itertools import chain

        return Tags(chain.from_iterable(kw.tags for kw in self.keywords))


class KeywordDoc(object):
    def __init__(self, name="", args=(), doc="", tags=()):
        self.name = name
        self.args = args
        self.doc = doc
        self.tags = Tags(tags)


class SpecDocBuilder(object):
    def build(self, path):
        spec = self._parse_spec(path)
        libdoc = LibraryDoc(
            name=spec.get("name"),
            type=spec.get("type"),
            version=spec.find("version").text or "",
            doc=spec.find("doc").text or "",
            scope=spec.find("scope").text or "",
            named_args=self._get_named_args(spec),
            doc_format=spec.get("format", "ROBOT"),
        )
        libdoc.inits = self._create_keywords(spec, "init")
        libdoc.keywords = self._create_keywords(spec, "kw")
        return libdoc

    def _parse_spec(self, path):
        if not os.path.isfile(path):
            raise IOError("Spec file '%s' does not exist." % path)
        root = ET.parse(path).getroot()
        if root.tag != "keywordspec":
            raise RuntimeError("Invalid spec file '%s'." % path)
        return root

    def _get_named_args(self, spec):
        elem = spec.find("namedargs")
        if elem is None:
            return False  # Backwards compatiblity with RF < 2.6.2
        return elem.text == "yes"

    def _create_keywords(self, spec, path):
        return [self._create_keyword(elem) for elem in spec.findall(path)]

    def _create_keyword(self, elem):
        return KeywordDoc(
            name=elem.get("name", ""),
            args=[a.text for a in elem.findall("arguments/arg")],
            doc=elem.find("doc").text or "",
            tags=[t.text for t in elem.findall("tags/tag")],
        )