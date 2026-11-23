from dataclasses import dataclass

from exact import Point, point, twice_signed_area


@dataclass(frozen=True)
class SourceTriangle:
    vertices: tuple[Point, Point, Point]


def validate_triangle(vertices):
    if not isinstance(vertices, (list, tuple)) or len(vertices) != 3:
        raise ValueError('a source triangle requires three vertices')
    triangle = SourceTriangle(tuple(point(vertex) for vertex in vertices))
    if twice_signed_area(triangle.vertices) == 0:
        raise ValueError('source triangle must have nonzero area')
    return triangle
