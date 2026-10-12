extends SceneTree
## Execute shared polygon geometry cases without images or drawing.

const PolygonGeometry = preload("res://scripts/polygon_geometry.gd")


func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected request and result JSON filenames")
		quit(1)
		return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(arguments[0])) != OK or not parser.data is Array:
		push_error("Invalid polygon test requests")
		quit(1)
		return
	var reader := PolygonGeometry.new()
	var results: Array = []
	for request in parser.data:
		var document: Variant = request.document
		if request.has("non_finite"):
			document[0].points[0][0] = NAN if request.non_finite == "nan" else (-INF if request.non_finite == "negative-inf" else INF)
		if request.has("native_int"):
			document[0].points[0][0] = str(request.native_int).to_int()
		var before := JSON.stringify(document)
		var result := reader.parse(document)
		if JSON.stringify(document) != before:
			push_error("Polygon validation modified its input")
			quit(1)
			return
		if reader.error.is_empty():
			var expected := JSON.stringify(result)
			if not result.is_empty():
				for layer in result:
					for point in layer.points:
						if not point[0] is int or not point[1] is int:
							push_error("Coordinates were not normalized to integers")
							quit(1)
							return
				result[0].points[0][0] = -999
				result[0].color[0] = -1
				if result[0].get("extra") is Dictionary and result[0].extra.get("values") is Array:
					result[0].extra.values.append("changed")
			if JSON.stringify(document) != before:
				push_error("Returned polygon aliases its input")
				quit(1)
				return
			results.append({"id": request.id, "status": "accepted", "result": JSON.parse_string(expected)})
		else:
			if not result.is_empty():
				push_error("Failed polygon validation returned partial data")
				quit(1)
				return
			results.append({"id": request.id, "status": "rejected", "error": reader.error})
	var report := FileAccess.open(arguments[1], FileAccess.WRITE)
	if report == null:
		push_error("Cannot write polygon test report")
		quit(1)
		return
	report.store_string(JSON.stringify(results))
	report.close()
	print("GODOT_POLYGON_TESTS cases=", results.size())
	quit(0)
