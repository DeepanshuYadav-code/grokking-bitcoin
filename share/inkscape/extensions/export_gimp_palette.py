#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (c) 2009 - Jos Hirth, kaioa.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Export a gimp pallet file (.gpl)
"""

import inkex
from inkex import ShapeElement, ColorIdError, ColorError


class ExportGimpPalette(inkex.OutputExtension):
    """Export all colors in a document to a gimp pallet"""

    select_all = (ShapeElement,)
    names = {}

    def save(self, stream):
        name = self.svg.name.replace(".svg", "")
        stream.write("GIMP Palette\nName: {}\n#\n".format(name).encode("utf-8"))

        for key, value in sorted(list(set(self.get_colors()))):
            stream.write("{} {}\n".format(key, value).encode("utf-8"))

    def get_colors(self):
        """Get all the colors from the selected elements"""
        for elem in self.svg.selection.filter(ShapeElement):
            for color in self.process_element(elem):
                if str(color).upper() == "NONE":
                    continue
                yield (
                    "{:3d} {:3d} {:3d}".format(*color.to_rgb()),
                    self.names.get(color) or str(color).upper(),
                )

    def process_element(self, elem):
        """Recursively process elements for colors"""
        style = elem.specified_style()
        for col in inkex.Style.color_props:
            try:
                color = style(col)
                if isinstance(color, inkex.Color):
                    if (
                        elem.getparent().get("inkscape:swatch") == "solid"
                        and col == "stop-color"
                    ):
                        self.names[color] = elem.getparent().get_id()
                    yield color
                elif isinstance(color, inkex.Gradient):
                    for stop in color.stops:
                        for item in self.process_element(stop):
                            yield item
            except ColorError:
                pass  # Bad color

        if (
            elem.href is not None
        ):  # Capture colors of symbols or clones pointing to defs
            for color in self.process_element(elem.href):
                yield color


if __name__ == "__main__":
    ExportGimpPalette().run()
