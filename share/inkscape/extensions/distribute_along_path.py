#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2006 Jean-Francois Barraud, barraud@math.univ-lille1.fr
#               2021 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# barraud@math.univ-lille1.fr
"""
This script scatters an object (the pattern) along other paths (skeletons)...
The topmost selected object is the pattern
the other selected ones are the skeletons.

No deformation is applied to the pattern itself.
"""

import random
import math
import numpy as np

import inkex
from inkex import bezier, Transform, BoundingBox, Group, Use
from inkex.localization import inkex_gettext as _

import pathmodifier


class DistributeAlongPath(pathmodifier.Diffeo):
    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument(
            "-n",
            "--noffset",
            type=float,
            dest="noffset",
            default=0.0,
            help="normal offset",
        )
        self.arg_parser.add_argument(
            "-t",
            "--toffset",
            type=float,
            dest="toffset",
            default=0.0,
            help="tangential offset",
        )
        self.arg_parser.add_argument(
            "-g",
            "--grouppick",
            type=inkex.Boolean,
            dest="grouppick",
            default=False,
            help="if pattern is a group then randomly pick group members",
        )
        self.arg_parser.add_argument(
            "-m",
            "--pickmode",
            type=str,
            dest="pickmode",
            default="rand",
            help="group pick mode (rand=random seq=sequentially)",
        )
        self.arg_parser.add_argument(
            "-f",
            "--follow",
            type=inkex.Boolean,
            dest="follow",
            default=True,
            help="choose between wave or snake effect",
        )
        self.arg_parser.add_argument(
            "-s",
            "--stretch",
            type=inkex.Boolean,
            dest="stretch",
            default=False,
            help="repeat the path to fit deformer's length",
        )
        self.arg_parser.add_argument(
            "-p", "--space", type=float, dest="space", default=0.0
        )
        self.arg_parser.add_argument(
            "-r",
            "--rotate",
            type=inkex.Boolean,
            dest="vertical",
            default=False,
            help="reference path is vertical",
        )
        self.arg_parser.add_argument(
            "-c",
            "--copymode",
            type=str,
            dest="copymode",
            default="move",
            help="""How the pattern is duplicated. Default: 'move',
                                     Options: 'clone', 'duplicate', 'move'""",
        )
        self.arg_parser.add_argument(
            "--tab",
            type=str,
            dest="tab",
            help="The selected UI-tab when OK was pressed",
        )

    def localTransformAt(self, s, skelcomp, lengths, isclosed, follow=True):
        """
        receives a length, and returns the corresponding point and tangent of skelcomp
        if follow is set to false, returns only the translation
        """
        i, t = self.lengthtotime(s, lengths, isclosed)
        if i == len(skelcomp) - 1:
            x, y = bezier.between_point(skelcomp[i - 1], skelcomp[i], 1 + t)
            dx = (skelcomp[i][0] - skelcomp[i - 1][0]) / lengths[-1]
            dy = (skelcomp[i][1] - skelcomp[i - 1][1]) / lengths[-1]
        else:
            x, y = bezier.between_point(skelcomp[i], skelcomp[i + 1], t)
            dx = (skelcomp[i + 1][0] - skelcomp[i][0]) / lengths[i]
            dy = (skelcomp[i + 1][1] - skelcomp[i][1]) / lengths[i]
        if follow:
            mat = [[dx, -dy, x], [dy, dx, y]]
        else:
            mat = [[1, 0, x], [0, 1, y]]
        return Transform(mat)

    def center_node_at_origin(self, node):
        """Translates a node to the origin and applies translation if requested"""
        bbox = node.bounding_box()
        mat = Transform([[1, 0, -bbox.center.x], [0, 1, -bbox.center.y]])
        if self.options.vertical:
            bbox = BoundingBox(-bbox.y, -bbox.x)
            mat = Transform([[0, -1, 0], [1, 0, 0]]) @ mat
        mat.add_translate([0, self.options.noffset])
        node.transform = mat @ node.transform
        return bbox

    def effect(self):
        if len(self.svg.selection) < 2:
            inkex.errormsg(_("This extension requires two selected paths."))
            return
        original_pattern_node, skeletons = self.get_patterns_and_skeletons(False, False)

        g_node = Group()
        original_pattern_node.getparent().append(g_node)

        if self.options.copymode == "clone":
            pattern_node = g_node.add(Use())
            pattern_node.href = original_pattern_node
        else:
            pattern_node = original_pattern_node.duplicate()

        # We will later compute transforms relative to the origin
        bbox = self.center_node_at_origin(pattern_node)

        width = bbox.width
        dx = width + self.options.space
        if dx < 0.01:
            if isinstance(original_pattern_node, inkex.TextElement):
                raise inkex.AbortExtension(_("Please convert texts to path first"))
            raise inkex.AbortExtension(
                _(
                    "The total length of the pattern is too small\n"
                    "Please choose a larger object or set 'Space between copies' > 0"
                )
            )

        # check if group and expand it
        pattern_list = []
        if self.options.grouppick and isinstance(pattern_node, Group):
            mat = pattern_node.transform
            for child in pattern_node:
                child.transform = mat @ child.transform
                pattern_list.append(child)
        else:
            pattern_list.append(pattern_node)

        self._do_transform(skeletons, width, pattern_list, g_node)

        if self.options.copymode == "move":
            original_pattern_node.getparent().remove(original_pattern_node)
        # pattern_node was just a temporary copy, definitely remove this
        pattern_node.getparent().remove(pattern_node)

    def _do_transform(self, skeletons, width, pattern_list, g_node):
        counter = 0
        for skelnode in skeletons.values():
            skelnode.apply_transform()
            for subpath in skelnode.path.break_apart():
                skelcomp, lengths = self.linearize(subpath.to_superpath()[0])
                skel_closed = all(
                    [math.isclose(i, j) for i, j in zip(skelcomp[0], skelcomp[-1])]
                )

                length = sum(lengths)
                dx = width + self.options.space
                if self.options.stretch:
                    if subpath[-1].letter in "zZ":
                        sval = np.linspace(
                            0,
                            length,
                            int((length + self.options.space) / (dx)),
                            endpoint=False,
                        )
                    else:
                        sval = np.linspace(
                            0,
                            length,
                            int((length + self.options.space) / (dx)) + 1,
                            endpoint=True,
                        )
                else:
                    sval = [self.options.toffset * 0.01 * dx]
                    while sval[-1] + dx < length:
                        sval.append(sval[-1] + dx)

                for counter, s in enumerate(sval):
                    local_transform = self.localTransformAt(
                        s, skelcomp, lengths, skel_closed, self.options.follow
                    )

                    pattern_idx = (
                        random.randint(0, len(pattern_list) - 1)
                        if self.options.pickmode == "rand"
                        else counter % len(pattern_list)
                    )

                    clone = pattern_list[pattern_idx].copy()

                    g_node.append(clone)

                    clone.transform = local_transform @ clone.transform


if __name__ == "__main__":
    DistributeAlongPath().run()
