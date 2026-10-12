extends RefCounted
## Read-only polygon shape/integer coordinates, independent of colors/drawing.

const MAX_EXACT_INTEGER: int = 9007199254740991
var error: String = ""


func coordinate(value: Variant, label: String) -> int:
	if not (value is int or value is float) or not is_finite(float(value)):
		error = label + " must be a finite integer value"
		return 0
	var number := float(value)
	if number < -MAX_EXACT_INTEGER or number > MAX_EXACT_INTEGER or floor(number) != number:
		error = label + " must be an exact integer value within +/- (2^53-1)"
		return 0
	return int(value)


func parse(raw: Variant) -> Array:
	error = ""
	if not raw is Array:
		error = "background.polygons must be an array"
		return []
	var result: Array = raw.duplicate(true)
	for index in raw.size():
		var layer: Variant = raw[index]
		var label := "background.polygons[%d]" % index
		if not layer is Dictionary or not layer.get("points") is Array or layer.points.size() < 3:
			error = label + ".points must contain at least three points"
			return []
		for point_index in layer.points.size():
			var point: Variant = layer.points[point_index]
			var point_label := label + ".points[%d]" % point_index
			if not point is Array or point.size() != 2:
				error = point_label + " must contain x and y"
				return []
			var x := coordinate(point[0], point_label + " x")
			if not error.is_empty():
				return []
			var y := coordinate(point[1], point_label + " y")
			if not error.is_empty():
				return []
			result[index].points[point_index] = [x, y]
	return result
