extends SceneTree
## Batch the real GDScript room parser for the shared Python test oracle.

const RoomGeometry = preload("res://scripts/room_geometry.gd")


func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected request and result JSON filenames")
		quit(1)
		return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(arguments[0])) != OK or not parser.data is Array:
		push_error("Invalid room test requests")
		quit(1)
		return
	var results: Array = []
	var reader := RoomGeometry.new()
	for request in parser.data:
		var document: Variant = request.document
		if request.has("non_finite"):
			match request.non_finite:
				"width": document.size.width = NAN
				"movement": document.movement_bounds[0] = INF
				"water": document.zones.water_rest[2] = NAN
				"fps": document.fps = INF
				"distance": document.conversation_distance = NAN
		var before := JSON.stringify(document)
		var result := reader.parse(document)
		if JSON.stringify(document) != before:
			push_error("Room validation modified its input")
			quit(1)
			return
		if reader.error.is_empty():
			# The returned room must also be a deep copy, including untouched metadata.
			var expected := JSON.stringify(result)
			result.size.width = 0
			result.zones.water_rest[0] = -1
			if result.has("metadata"):
				result["metadata"]["values"].append("changed")
			if JSON.stringify(document) != before:
				push_error("Returned room aliases its input")
				quit(1)
				return
			results.append({"id": request.id, "status": "accepted", "result": JSON.parse_string(expected)})
		else:
			if not result.is_empty():
				push_error("Failed room validation returned partial data")
				quit(1)
				return
			results.append({"id": request.id, "status": "rejected", "error": reader.error})
	var report := FileAccess.open(arguments[1], FileAccess.WRITE)
	if report == null:
		push_error("Cannot write room test report")
		quit(1)
		return
	report.store_string(JSON.stringify(results))
	report.close()
	print("GODOT_ROOM_TESTS cases=", results.size())
	quit(0)
