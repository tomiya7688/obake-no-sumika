extends SceneTree
## Report the real character adapter's results for the shared Python oracle.

const CharacterSchema = preload("res://scripts/character_schema.gd")


func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected request and result JSON filenames")
		quit(1)
		return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(arguments[0])) != OK or not parser.data is Array:
		push_error("Invalid character test requests")
		quit(1)
		return
	var results: Array = []
	var reader := CharacterSchema.new()
	for request in parser.data:
		var document: Variant = request.document
		if request.has("non_finite"):
			document.characters[0][request.non_finite] = NAN
		var before := JSON.stringify(document)
		var result := reader.parse(document, Vector2i(request.room_size[0], request.room_size[1]))
		if JSON.stringify(document) != before:
			push_error("Character validation modified its input")
			quit(1)
			return
		if reader.error.is_empty():
			results.append({"id": request.id, "status": "accepted", "result": result})
		else:
			if not result.is_empty():
				push_error("Failed character validation returned partial data")
				quit(1)
				return
			results.append({"id": request.id, "status": "rejected", "error": reader.error})
	var report := FileAccess.open(arguments[1], FileAccess.WRITE)
	if report == null:
		push_error("Cannot write character test report")
		quit(1)
		return
	report.store_string(JSON.stringify(results))
	report.close()
	print("GODOT_CHARACTER_TESTS cases=", results.size())
	quit(0)
