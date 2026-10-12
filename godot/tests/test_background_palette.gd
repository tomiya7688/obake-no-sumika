extends SceneTree
## Run the real palette adapter against shared JSON requests.

const BackgroundPalette = preload("res://scripts/background_palette.gd")


func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected request and result JSON filenames")
		quit(1)
		return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(arguments[0])) != OK or not parser.data is Array:
		push_error("Invalid palette test requests")
		quit(1)
		return
	var reader := BackgroundPalette.new()
	var results: Array = []
	for request in parser.data:
		var document: Variant = request.document
		if request.has("non_finite"):
			match request.non_finite:
				"top": document.gradient.top[0] = NAN
				"bottom": document.gradient.bottom[2] = INF
				"step": document.gradient.step = INF
				"polygon": document.polygons[0].color[1] = NAN
		var before := JSON.stringify(document)
		var result := reader.parse(document, int(request.room_height))
		if JSON.stringify(document) != before:
			push_error("Palette validation modified its input")
			quit(1)
			return
		if reader.error.is_empty():
			var expected := JSON.stringify(result)
			result.gradient.top[0] = -1
			if not result.polygons.is_empty():
				var points: Variant = result.polygons[0].get("points")
				if points is Array and not points.is_empty() and points[0] is Array and not points[0].is_empty():
					points[0][0] = -999
			if result.get("metadata") is Dictionary and result.metadata.get("values") is Array:
				result["metadata"]["values"].append("changed")
			if JSON.stringify(document) != before:
				push_error("Returned palette aliases its input")
				quit(1)
				return
			results.append({"id": request.id, "status": "accepted", "result": JSON.parse_string(expected)})
		else:
			if not result.is_empty():
				push_error("Failed palette validation returned partial data")
				quit(1)
				return
			results.append({"id": request.id, "status": "rejected", "error": reader.error})
	var report := FileAccess.open(arguments[1], FileAccess.WRITE)
	if report == null:
		push_error("Cannot write palette test report")
		quit(1)
		return
	report.store_string(JSON.stringify(results))
	report.close()
	print("GODOT_PALETTE_TESTS cases=", results.size())
	quit(0)
